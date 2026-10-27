"""Métriques d'évaluation classification NLP."""

from __future__ import annotations

from typing import Sequence

from sklearn.metrics import accuracy_score, classification_report, f1_score


def compute_metrics(
    y_true: Sequence[str],
    y_pred: Sequence[str],
    labels: Sequence[str],
) -> dict:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "f1_macro": float(
            f1_score(y_true, y_pred, labels=list(labels), average="macro", zero_division=0)
        ),
        "f1_weighted": float(
            f1_score(y_true, y_pred, labels=list(labels), average="weighted", zero_division=0)
        ),
        "report": classification_report(
            y_true, y_pred, labels=list(labels), zero_division=0, output_dict=True
        ),
    }


def metrics_summary(metrics: dict) -> str:
    return (
        f"accuracy={metrics['accuracy']:.3f} "
        f"f1_macro={metrics['f1_macro']:.3f} "
        f"f1_weighted={metrics['f1_weighted']:.3f}"
    )
