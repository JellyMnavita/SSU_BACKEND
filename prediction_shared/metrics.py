"""Métriques d'évaluation — classification 3 classes (degré de danger)."""

from __future__ import annotations

from typing import Sequence

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

from prediction_shared.labels import CLASS_NAMES


def compute_metrics(
    y_true: Sequence[int],
    y_pred: Sequence[int],
    *,
    labels: Sequence[int] | None = None,
) -> dict:
    label_ids = list(labels) if labels is not None else [0, 1, 2]
    label_names = [CLASS_NAMES[i] for i in label_ids]

    cm = confusion_matrix(y_true, y_pred, labels=label_ids).tolist()
    report = classification_report(
        y_true,
        y_pred,
        labels=label_ids,
        target_names=label_names,
        zero_division=0,
        output_dict=True,
    )

    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "f1_macro": float(
            f1_score(y_true, y_pred, labels=label_ids, average="macro", zero_division=0)
        ),
        "f1_weighted": float(
            f1_score(y_true, y_pred, labels=label_ids, average="weighted", zero_division=0)
        ),
        "precision_macro": float(
            precision_score(y_true, y_pred, labels=label_ids, average="macro", zero_division=0)
        ),
        "recall_macro": float(
            recall_score(y_true, y_pred, labels=label_ids, average="macro", zero_division=0)
        ),
        "confusion_matrix": cm,
        "labels_order": label_names,
        "report": report,
    }


def metrics_summary(metrics: dict) -> str:
    return (
        f"accuracy={metrics['accuracy']:.3f} "
        f"f1_macro={metrics['f1_macro']:.3f} "
        f"f1_weighted={metrics['f1_weighted']:.3f}"
    )


def sample_weights(y: np.ndarray) -> np.ndarray:
    """Poids inversement proportionnels à la fréquence de classe."""
    counts = np.bincount(y, minlength=3)
    total = max(len(y), 1)
    return np.array([total / max(counts[label], 1) for label in y], dtype=float)
