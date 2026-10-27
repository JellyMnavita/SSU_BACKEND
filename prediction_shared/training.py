"""Entraînement, nettoyage, FE post-split, HPO et sélection de modèles."""

from __future__ import annotations

import json
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import (
    ExtraTreesClassifier,
    GradientBoostingClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import (
    RandomizedSearchCV,
    StratifiedKFold,
)
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from prediction_shared.dataset import (
    build_splits,
    load_gold_eval,
    load_split,
    models_dir,
    production_model_dir,
)
from prediction_shared.features import build_feature_matrix, feature_target_correlations
from prediction_shared.labels import CLASS_NAMES_FR, FEATURE_LABELS_FR, FEATURE_NAMES, feature_catalog_for_admin
from prediction_shared.metrics import compute_metrics, sample_weights

CV_FOLDS_MAX = 5
RANDOM_STATE = 42
HPO_N_ITER = 8


def _silence_sklearn_noise() -> None:
    warnings.filterwarnings(
        "ignore",
        message=".*multi_class.*",
        category=FutureWarning,
    )
    warnings.filterwarnings(
        "ignore",
        message=".*iprint.*",
    )
    warnings.filterwarnings(
        "ignore",
        message=".*Unknown solver options: iprint.*",
    )
    warnings.filterwarnings(
        "ignore",
        category=FutureWarning,
        module=r"sklearn\.linear_model\._logistic",
    )
    try:
        from scipy.optimize import OptimizeWarning

        warnings.filterwarnings("ignore", category=OptimizeWarning)
    except ImportError:
        pass


def _adaptive_n_splits(y: np.ndarray, requested: int = CV_FOLDS_MAX) -> int:
    """CV stratifiée : plis ≤ effectif de la classe la plus rare."""
    _, counts = np.unique(y, return_counts=True)
    min_count = int(counts.min()) if len(counts) else 1
    return max(2, min(requested, min_count))


def _base_estimators() -> dict[str, Any]:
    """Six modèles modernes sklearn, hyperparamètres de base."""
    return {
        "HistGradientBoosting": HistGradientBoostingClassifier(
            max_iter=150,
            learning_rate=0.1,
            max_depth=6,
            random_state=RANDOM_STATE,
        ),
        "GradientBoosting": GradientBoostingClassifier(
            n_estimators=120,
            learning_rate=0.1,
            max_depth=4,
            random_state=RANDOM_STATE,
        ),
        "RandomForest": RandomForestClassifier(
            n_estimators=200,
            max_depth=10,
            class_weight="balanced",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
        "ExtraTrees": ExtraTreesClassifier(
            n_estimators=250,
            max_depth=12,
            class_weight="balanced",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
        "LogisticRegression": LogisticRegression(
            max_iter=2000,
            class_weight="balanced",
            random_state=RANDOM_STATE,
            solver="lbfgs",
        ),
        "SVM": SVC(
            kernel="rbf",
            C=1.0,
            gamma="scale",
            class_weight="balanced",
            probability=True,
            random_state=RANDOM_STATE,
        ),
    }


def _param_distributions() -> dict[str, dict[str, list[Any]]]:
    return {
        "HistGradientBoosting": {
            "max_iter": [80, 120, 200],
            "learning_rate": [0.05, 0.1, 0.15],
            "max_depth": [3, 5, 8],
            "min_samples_leaf": [5, 10, 20],
        },
        "GradientBoosting": {
            "n_estimators": [80, 120, 180],
            "learning_rate": [0.05, 0.1, 0.15],
            "max_depth": [2, 3, 5],
            "subsample": [0.8, 1.0],
        },
        "RandomForest": {
            "n_estimators": [120, 200, 300],
            "max_depth": [6, 10, 14, None],
            "min_samples_leaf": [1, 2, 4],
        },
        "ExtraTrees": {
            "n_estimators": [150, 250, 350],
            "max_depth": [8, 12, None],
            "min_samples_leaf": [1, 2, 4],
        },
        "LogisticRegression": {
            "C": [0.1, 0.5, 1.0, 2.0, 5.0],
        },
        "SVM": {
            "C": [0.5, 1.0, 2.0, 5.0],
            "gamma": ["scale", "auto", 0.05, 0.1],
        },
    }


def cross_validate_models(
    X: np.ndarray,
    y: np.ndarray,
    *,
    n_splits: int | None = None,
    tune: bool = True,
) -> dict[str, Any]:
    """Compare 6 candidats avec validation croisée + recherche d'hyperparamètres."""
    _silence_sklearn_noise()
    folds = n_splits or _adaptive_n_splits(y)
    cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=RANDOM_STATE)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    comparison: dict[str, Any] = {}
    best_params: dict[str, Any] = {}
    param_grids = _param_distributions()

    for name, estimator in _base_estimators().items():
        if tune and name in param_grids:
            n_iter = min(HPO_N_ITER, int(np.prod([len(v) for v in param_grids[name].values()])))
            search = RandomizedSearchCV(
                estimator,
                param_distributions=param_grids[name],
                n_iter=max(1, n_iter),
                scoring="f1_macro",
                cv=cv,
                random_state=RANDOM_STATE,
                # n_jobs=1 pour la logistique : évite des OptimizeWarning iprint dans les workers joblib
                n_jobs=1 if name == "LogisticRegression" else -1,
                refit=True,
                error_score=np.nan,
            )
            with warnings.catch_warnings():
                _silence_sklearn_noise()
                warnings.simplefilter("ignore")
                search.fit(X_scaled, y)
            best_est = search.best_estimator_
            best_params[name] = search.best_params_
            # Scores CV du meilleur couple d'hyperparamètres
            mean_f1 = float(search.best_score_) if search.best_score_ == search.best_score_ else 0.0
            std_f1 = float(
                np.nanstd(
                    [
                        search.cv_results_["split%d_test_score" % i][search.best_index_]
                        for i in range(folds)
                        if f"split{i}_test_score" in search.cv_results_
                    ]
                )
            )
            # Accuracy séparée
            from sklearn.model_selection import cross_val_score

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                acc_scores = cross_val_score(
                    best_est, X_scaled, y, cv=cv, scoring="accuracy", n_jobs=-1
                )
            comparison[name] = {
                "accuracy_mean": float(np.mean(acc_scores)),
                "accuracy_std": float(np.std(acc_scores)),
                "f1_macro_mean": mean_f1,
                "f1_macro_std": std_f1,
                "folds": folds,
                "tuned": True,
                "best_params": best_params[name],
            }
        else:
            from sklearn.model_selection import cross_validate

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                cv_result = cross_validate(
                    estimator,
                    X_scaled,
                    y,
                    cv=cv,
                    scoring={"accuracy": "accuracy", "f1_macro": "f1_macro"},
                    n_jobs=-1,
                    error_score="raise",
                )
            comparison[name] = {
                "accuracy_mean": float(np.mean(cv_result["test_accuracy"])),
                "accuracy_std": float(np.std(cv_result["test_accuracy"])),
                "f1_macro_mean": float(np.mean(cv_result["test_f1_macro"])),
                "f1_macro_std": float(np.std(cv_result["test_f1_macro"])),
                "folds": folds,
                "tuned": False,
                "best_params": {},
            }
            best_params[name] = {}

    # Ordre stable : F1 ↓, précision ↓, puis ordre de déclaration (HistGradientBoosting en 1er).
    declare_order = {name: i for i, name in enumerate(_base_estimators())}
    ranked = sorted(
        comparison.items(),
        key=lambda item: (
            -item[1]["f1_macro_mean"],
            -item[1]["accuracy_mean"],
            declare_order.get(item[0], 99),
        ),
    )
    winner = ranked[0][0]
    # Si plusieurs modèles sont à égalité (écarts < 1e-6), le nomme clairement.
    top_f1 = comparison[winner]["f1_macro_mean"]
    tied = [
        name
        for name, _ in ranked
        if abs(comparison[name]["f1_macro_mean"] - top_f1) < 1e-6
    ]
    tie_note = (
        f" (égalité F1 avec {', '.join(tied[1:])} — départage par ordre de priorité)"
        if len(tied) > 1
        else ""
    )
    return {
        "comparison": comparison,
        "ranking": [name for name, _ in ranked],
        "selected_model": winner,
        "best_params": best_params,
        "cv_folds": folds,
        "selection_reason": (
            f"Meilleur F1 macro en validation croisée ({folds}-fold) "
            f"avec optimisation d'hyperparamètres : {winner} "
            f"(F1={comparison[winner]['f1_macro_mean']:.3f} ± "
            f"{comparison[winner]['f1_macro_std']:.3f})"
            f"{tie_note}"
        ),
    }


def fit_selected_model(
    name: str,
    X: np.ndarray,
    y: np.ndarray,
    *,
    params: dict[str, Any] | None = None,
) -> tuple[Any, StandardScaler]:
    _silence_sklearn_noise()
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    model = _base_estimators()[name]
    if params:
        model.set_params(**params)
    weights = sample_weights(y)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if name == "GradientBoosting":
            model.fit(X_scaled, y, sample_weight=weights)
        else:
            model.fit(X_scaled, y)
    return model, scaler


def evaluate_on_frame(
    model: Any,
    scaler: StandardScaler,
    df: pd.DataFrame,
) -> dict:
    if df is None or len(df) == 0:
        return {}
    X, y = build_feature_matrix(df, exclude_self=True)
    preds = model.predict(scaler.transform(X))
    return compute_metrics(y, preds)


def _plain_language_report(summary: dict[str, Any]) -> dict[str, Any]:
    cleaning = summary.get("cleaning", {})
    winner = summary.get("algorithm", "—")
    f1 = (
        summary.get("comparison", {})
        .get(winner, {})
        .get("f1_macro_mean")
    )
    steps = [
        "1. Nettoyage des données : coordonnées invalides retirées, doublons supprimés, "
        "dates manquantes remplacées, degrés normalisés (F/M/E).",
        "2. Découpage train / validation / test / gold (sans fuite des synthétiques hors train).",
        "3. Construction des variables de base (position, heure, densité = comptage de voisins, "
        "distance au voisin le plus proche). Pas de degré moyen des voisins : le degré est la cible. "
        "Puis enrichissement (nuit, week-end, cycles sin/cos, densités, distance au centre).",
        "4. Corrélations calculées uniquement sur le train pour juger la pertinence.",
        "5. Comparaison de 6 modèles modernes avec recherche d'hyperparamètres ; "
        f"le gagnant est {winner}"
        + (f" (F1 macro ≈ {f1:.3f})." if isinstance(f1, (int, float)) else "."),
        "6. Réentraînement final sur train+val, sauvegarde best_model.pkl + scaler.pkl.",
    ]
    ranking_lines = []
    for i, name in enumerate(summary.get("ranking", []), start=1):
        m = summary.get("comparison", {}).get(name, {})
        ranking_lines.append(
            {
                "rang": i,
                "modele": name,
                "f1_macro": round(m.get("f1_macro_mean", 0), 3),
                "precision_globale": round(m.get("accuracy_mean", 0), 3),
                "hyperparametres": m.get("best_params") or {},
            }
        )
    return {
        "resume": (
            f"Modèle retenu : {winner}. "
            f"Échantillons utilisés pour l'ajustement final : "
            f"{summary.get('samples', {}).get('fit_total', 0)}. "
            f"Variables : {len(summary.get('features', FEATURE_NAMES))}."
        ),
        "etapes": steps,
        "nettoyage": {
            "lignes_lues": cleaning.get("rows_read", 0),
            "lignes_conservees": cleaning.get("rows_kept", 0),
            "doublons_supprimes": cleaning.get("removed_duplicates", 0),
            "coords_invalides": cleaning.get("removed_invalid_coords", 0),
            "hors_kinshasa": cleaning.get("removed_out_of_bbox", 0),
            "degres_invalides": cleaning.get("removed_invalid_degree", 0),
            "dates_remplies": cleaning.get("filled_created_at", 0),
        },
        "classement_modeles": ranking_lines,
        "variables": feature_catalog_for_admin(),
        "classes": CLASS_NAMES_FR,
    }


def run_training_pipeline(
    data_dir: Path | None = None,
    *,
    rebuild_splits: bool = True,
    tune: bool = True,
) -> dict[str, Any]:
    """
    Pipeline : nettoyage → split → FE (après split) → corrélations train →
    CV + HPO sur 6 modèles → fit final → évaluation → artefacts.
    """
    _silence_sklearn_noise()
    root = data_dir
    if rebuild_splits:
        split_result = build_splits(root, write=True)
        train_df = split_result["train"]
        val_df = split_result["val"]
        test_df = split_result["test"]
        gold_df = split_result["gold"]
        profile = split_result["profile"]
    else:
        train_df = load_split("train", root)
        val_df = load_split("val", root)
        test_df = load_split("test", root)
        gold_df = load_gold_eval(root)
        from prediction_shared.dataset import build_dataset_profile

        profile = build_dataset_profile(root)

    if train_df.empty:
        raise ValueError("Jeu train vide — exportez des signalements validés.")

    # Feature engineering APRÈS le split (chaque matrice construite sur son split)
    X_train, y_train = build_feature_matrix(train_df, exclude_self=True)
    correlations = feature_target_correlations(X_train, y_train)

    cv_result = cross_validate_models(X_train, y_train, tune=tune)

    winner = cv_result["selected_model"]
    winner_params = cv_result.get("best_params", {}).get(winner) or {}
    train_val_df = pd.concat([train_df, val_df], ignore_index=True)
    X_fit, y_fit = build_feature_matrix(train_val_df, exclude_self=True)
    model, scaler = fit_selected_model(winner, X_fit, y_fit, params=winner_params)

    test_metrics = evaluate_on_frame(model, scaler, test_df)
    gold_metrics = evaluate_on_frame(model, scaler, gold_df)

    prod_dir = production_model_dir(root)
    prod_dir.mkdir(parents=True, exist_ok=True)
    model_path = prod_dir / "best_model.pkl"
    scaler_path = prod_dir / "scaler.pkl"
    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)

    out_models = models_dir(root)
    out_models.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "status": "trained",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "algorithm": winner,
        "best_params": winner_params,
        "features": FEATURE_NAMES,
        "feature_labels_fr": FEATURE_LABELS_FR,
        "feature_catalog": feature_catalog_for_admin(),
        "feature_correlations_train": correlations,
        "cleaning": profile.get("cleaning", {}),
        "samples": {
            "train": len(train_df),
            "val": len(val_df),
            "test": len(test_df),
            "gold": len(gold_df),
            "fit_total": len(train_val_df),
        },
        "samples_used": len(train_val_df),
        "class_distribution": profile.get("class_distribution", {}),
        "split_policy": profile.get("split_policy", {}),
        "comparison": cv_result["comparison"],
        "ranking": cv_result["ranking"],
        "cv_folds": cv_result.get("cv_folds"),
        "selection_reason": cv_result["selection_reason"],
        "test_metrics": test_metrics,
        "gold_metrics": gold_metrics,
        "model_path": str(model_path),
        "scaler_path": str(scaler_path),
        "pipeline": {
            "cleaning": True,
            "deduplication": True,
            "missing_value_imputation": True,
            "feature_engineering_after_split": True,
            "hyperparameter_optimization": tune,
            "model_count": len(cv_result["ranking"]),
            "selection_metric": "f1_macro",
        },
    }
    summary["plain_language"] = _plain_language_report(summary)

    active = {
        "algorithm": winner,
        "best_params": winner_params,
        "trained_at": summary["trained_at"],
        "f1_macro_cv": cv_result["comparison"][winner]["f1_macro_mean"],
        "accuracy_cv": cv_result["comparison"][winner]["accuracy_mean"],
        "samples_used": len(train_val_df),
        "features": FEATURE_NAMES,
        "feature_catalog": feature_catalog_for_admin(),
        "selection_reason": cv_result["selection_reason"],
        "ranking": cv_result["ranking"],
        "model_path": str(model_path),
        "scaler_path": str(scaler_path),
    }

    with (out_models / "training_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
    with (out_models / "cv_results.json").open("w", encoding="utf-8") as handle:
        json.dump(cv_result, handle, ensure_ascii=False, indent=2)
    with (out_models / "gold_eval_results.json").open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "metrics": gold_metrics,
                "algorithm": winner,
                "samples": len(gold_df),
                "gold_real_only": bool(profile.get("split_policy", {}).get("gold_real_only")),
                "split_policy": profile.get("split_policy", {}),
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )
    with (prod_dir / "active_model.json").open("w", encoding="utf-8") as handle:
        json.dump(active, handle, ensure_ascii=False, indent=2)
    with (out_models / "active_model.json").open("w", encoding="utf-8") as handle:
        json.dump(active, handle, ensure_ascii=False, indent=2)

    return summary
