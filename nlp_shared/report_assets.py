"""Préparation partagée des données et graphiques pour rapport NLP PDF + Word."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from nlp_shared.evaluate import (
    evaluate_benign_cases,
    evaluate_rules_cases,
    fetch_training_registry,
    run_gold_evaluation,
)
from nlp_shared.lexicon_data import INCIDENT_TYPES
from nlp_shared.report_eda import (
    build_corpus_profile,
    generate_eda_plots,
    plot_confusion_matrix,
    plot_f1_per_class,
)
from nlp_shared.training.dataset import resolve_nlp_data_dir


def _load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


@dataclass
class NlpReportAssets:
    profile: dict
    training: dict
    gold: dict
    metrics: dict
    rules_eval: dict
    benign_eval: dict
    eda_plots: dict[str, Path] = field(default_factory=dict)
    cm_path: Path = field(default_factory=Path)
    f1_path: Path = field(default_factory=Path)
    reports_dir: Path = field(default_factory=Path)


def prepare_report_assets(
    data_dir: Path | None = None,
    *,
    api_url: str | None = None,
    skip_gold_eval: bool = False,
) -> NlpReportAssets:
    root = data_dir or resolve_nlp_data_dir()
    reports_dir = root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    models_dir = root / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    profile = build_corpus_profile(root)
    training = fetch_training_registry(api_url, root)
    if training:
        with (models_dir / "active_model.json").open("w", encoding="utf-8") as handle:
            json.dump(training, handle, ensure_ascii=False, indent=2)

    comparison = training.get("comparison") or {}
    eda_plots = generate_eda_plots(profile, reports_dir, comparison)

    gold = _load_json(models_dir / "gold_eval_results.json") or {}
    if not skip_gold_eval and not gold.get("metrics"):
        try:
            gold = run_gold_evaluation(root, api_url=api_url, models_dir=models_dir)
        except Exception as exc:
            gold = {"status": "error", "message": str(exc)}

    metrics = gold.get("metrics") or {}
    cm_path = reports_dir / "confusion_matrix_gold.png"
    if metrics.get("confusion_matrix"):
        plot_confusion_matrix(
            metrics["confusion_matrix"],
            metrics.get("labels_order") or list(INCIDENT_TYPES),
            cm_path,
            title="Matrice de confusion — gold_eval (pipeline complet)",
        )

    f1_path = reports_dir / "f1_per_class_gold.png"
    if metrics.get("report"):
        plot_f1_per_class(
            metrics["report"],
            metrics.get("labels_order") or list(INCIDENT_TYPES),
            f1_path,
        )

    rules_eval = evaluate_rules_cases(root)
    benign_eval = evaluate_benign_cases(root)

    manifest = {
        "generated_at": datetime.now().isoformat(),
        "profile": profile,
        "primary_ml": training.get("primary_ml"),
        "gold_f1_macro": metrics.get("f1_macro"),
        "rules_accuracy": rules_eval.get("accuracy"),
        "benign_accuracy": benign_eval.get("accuracy"),
        "plots": {k: str(v) for k, v in eda_plots.items()},
    }
    with (reports_dir / "report_manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)

    training_summary = {
        "primary_ml": training.get("primary_ml"),
        "ml_priority": training.get("ml_priority"),
        "trained_at": training.get("trained_at"),
        "data_source": training.get("data_source"),
        "comparison": comparison,
        "selection_reason": training.get("selection_reason"),
        "gold_f1_macro": metrics.get("f1_macro"),
    }
    with (models_dir / "training_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(training_summary, handle, ensure_ascii=False, indent=2)

    return NlpReportAssets(
        profile=profile,
        training=training,
        gold=gold,
        metrics=metrics,
        rules_eval=rules_eval,
        benign_eval=benign_eval,
        eda_plots=eda_plots,
        cm_path=cm_path,
        f1_path=f1_path,
        reports_dir=reports_dir,
    )
