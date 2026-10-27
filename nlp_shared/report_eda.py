"""Profil corpus et graphiques EDA pour le rapport NLP."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from nlp_shared.lexicon_data import INCIDENT_TYPES, RULES
from nlp_shared.training.dataset import load_corpus_splits, resolve_nlp_data_dir


def _load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _text_lengths(rows) -> list[int]:
    return [len((r.text if hasattr(r, "text") else r.get("text", "")).split()) for r in rows]


def build_corpus_profile(data_dir: Path | None = None) -> dict[str, Any]:
    root = data_dir or resolve_nlp_data_dir()
    stats = _load_json(root / "corpus_stats.json") or {}

    splits = load_corpus_splits(root)
    by_split: dict[str, dict[str, int]] = {}
    lengths: list[int] = []
    if splits:
        train, val, test = splits
        for name, rows in ("train", train), ("val", val), ("test", test):
            counts = {label: 0 for label in INCIDENT_TYPES}
            for row in rows:
                counts[row.label] = counts.get(row.label, 0) + 1
            by_split[name] = counts
            lengths.extend(_text_lengths(rows))

    gold = _load_json(root / "gold_eval.json") or []
    gold_by_label = {label: 0 for label in INCIDENT_TYPES}
    for row in gold:
        lbl = row.get("label", "")
        if lbl in gold_by_label:
            gold_by_label[lbl] += 1

    labels_total = stats.get("labels") or {}
    nonzero = [v for v in labels_total.values() if v > 0]
    imbalance = round(max(nonzero) / max(min(nonzero), 1), 2) if nonzero else 0.0

    return {
        "totals": {
            "all": stats.get("total", 0),
            "train": stats.get("train", 0),
            "val": stats.get("val", 0),
            "test": stats.get("test", 0),
            "gold": len(gold),
        },
        "sources": stats.get("sources") or {},
        "by_label": labels_total,
        "by_split": by_split,
        "gold_by_label": gold_by_label,
        "class_imbalance_ratio": imbalance,
        "text_length_words": {
            "mean": round(sum(lengths) / len(lengths), 1) if lengths else 0,
            "max": max(lengths) if lengths else 0,
            "min": min(lengths) if lengths else 0,
        },
        "rules_count": len(RULES),
        "incident_types": list(INCIDENT_TYPES),
    }


def _ensure_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def plot_label_distribution(profile: dict, out: Path) -> Path | None:
    plt = _ensure_matplotlib()
    labels = list(INCIDENT_TYPES)
    counts = [profile.get("by_label", {}).get(l, 0) for l in labels]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(labels, counts, color="#3b82f6")
    ax.set_title("Distribution des classes — corpus total")
    ax.set_ylabel("Nombre de textes")
    plt.xticks(rotation=30, ha="right")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out


def plot_model_comparison(comparison: dict, out: Path) -> Path | None:
    if not comparison:
        return None
    plt = _ensure_matplotlib()
    names = list(comparison.keys())
    val_scores = [float(comparison[n].get("val_f1_macro") or 0) for n in names]
    test_scores = [float(comparison[n].get("test_f1_macro") or 0) for n in names]
    x = range(len(names))
    width = 0.35
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar([i - width / 2 for i in x], val_scores, width, label="Val F1 macro", color="#6366f1")
    ax.bar([i + width / 2 for i in x], test_scores, width, label="Test F1 macro", color="#22c55e")
    ax.set_xticks(list(x))
    ax.set_xticklabels(names, rotation=15, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_title("Comparaison modèles ML — sélection Phase 3")
    ax.legend()
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out


def plot_confusion_matrix(matrix: list, labels: list[str], out: Path, title: str = "Matrice de confusion") -> Path | None:
    if not matrix:
        return None
    plt = _ensure_matplotlib()
    import numpy as np

    arr = np.array(matrix)
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(arr, cmap="Blues")
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_yticklabels(labels)
    ax.set_xlabel("Prédit")
    ax.set_ylabel("Vérité")
    ax.set_title(title)
    for i in range(arr.shape[0]):
        for j in range(arr.shape[1]):
            ax.text(j, i, str(arr[i, j]), ha="center", va="center", color="black", fontsize=8)
    fig.colorbar(im)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out


def plot_f1_per_class(report: dict, labels: list[str], out: Path) -> Path | None:
    if not report:
        return None
    plt = _ensure_matplotlib()
    scores = [float(report.get(l, {}).get("f1-score", 0)) for l in labels]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(labels, scores, color="#0ea5e9")
    ax.set_xlim(0, 1.05)
    ax.set_title("F1-score par classe — gold_eval")
    ax.set_xlabel("F1")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out


def generate_eda_plots(profile: dict, reports_dir: Path, comparison: dict | None = None) -> dict[str, Path]:
    plots: dict[str, Path] = {}
    p = plot_label_distribution(profile, reports_dir / "eda_label_distribution.png")
    if p:
        plots["label_distribution"] = p
    if comparison:
        p = plot_model_comparison(comparison, reports_dir / "eda_model_comparison.png")
        if p:
            plots["model_comparison"] = p
    return plots
