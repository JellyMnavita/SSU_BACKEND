"""Préparation partagée des assets pour rapport PDF + Word."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from prediction_shared.dataset import build_dataset_profile, resolve_prediction_data_dir
from prediction_shared.evaluate import load_gold_results, load_training_summary, run_gold_evaluation
from prediction_shared.report_eda import (
    build_eda_summary,
    generate_eda_plots,
    plot_confusion_matrix,
    plot_cv_comparison,
    plot_f1_per_class,
)


@dataclass
class PredictionReportAssets:
    profile: dict
    eda_summary: dict
    training: dict
    gold: dict
    metrics: dict
    test_metrics: dict
    eda_plots: dict[str, Path] = field(default_factory=dict)
    cm_path: Path = field(default_factory=Path)
    f1_path: Path = field(default_factory=Path)
    cv_path: Path = field(default_factory=Path)
    reports_dir: Path = field(default_factory=Path)


def prepare_report_assets(
    data_dir: Path | None = None,
    *,
    skip_gold_eval: bool = False,
    retrain_if_missing: bool = False,
) -> PredictionReportAssets:
    root = data_dir or resolve_prediction_data_dir()
    reports_dir = root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    models = root / "models"
    models.mkdir(parents=True, exist_ok=True)

    profile = build_dataset_profile(root)
    training = load_training_summary(root)

    if retrain_if_missing and not training:
        from prediction_shared.training import run_training_pipeline

        training = run_training_pipeline(root, rebuild_splits=True)

    comparison = training.get("comparison") or {}
    eda_plots = generate_eda_plots(profile, reports_dir, comparison=comparison)
    eda_summary = build_eda_summary(profile)

    gold = load_gold_results(root)
    if not skip_gold_eval and not gold.get("metrics"):
        try:
            gold = run_gold_evaluation(root)
        except Exception as exc:
            gold = {"status": "error", "message": str(exc)}

    metrics = gold.get("metrics") or {}
    test_metrics = training.get("test_metrics") or {}

    cm_path = reports_dir / "confusion_matrix_gold.png"
    if metrics.get("confusion_matrix"):
        plot_confusion_matrix(
            metrics["confusion_matrix"],
            metrics.get("labels_order") or ["faible", "modere", "eleve"],
            cm_path,
            title="Matrice de confusion — gold_eval",
        )

    f1_path = reports_dir / "f1_per_class_gold.png"
    if metrics.get("report"):
        plot_f1_per_class(
            metrics["report"],
            metrics.get("labels_order") or ["faible", "modere", "eleve"],
            f1_path,
        )

    cv_path = reports_dir / "cv_model_comparison.png"
    if comparison:
        plot_cv_comparison(comparison, cv_path)

    manifest = {
        "generated_at": datetime.now().isoformat(),
        "algorithm": training.get("algorithm"),
        "gold_f1_macro": metrics.get("f1_macro"),
        "test_f1_macro": test_metrics.get("f1_macro"),
        "samples": training.get("samples"),
        "plots": {k: str(v) for k, v in eda_plots.items()},
    }
    with (reports_dir / "report_manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)

    return PredictionReportAssets(
        profile=profile,
        eda_summary=eda_summary,
        training=training,
        gold=gold,
        metrics=metrics,
        test_metrics=test_metrics,
        eda_plots=eda_plots,
        cm_path=cm_path,
        f1_path=f1_path,
        cv_path=cv_path,
        reports_dir=reports_dir,
    )
