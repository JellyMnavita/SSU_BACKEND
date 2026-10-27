"""Profil dataset et graphiques EDA — prédiction spatiale."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from prediction_shared.dataset import build_dataset_profile, load_cleaned, resolve_prediction_data_dir
from prediction_shared.labels import CLASS_NAMES, CLASS_NAMES_FR, FEATURE_NAMES

PREPROCESSING_PIPELINE = [
    "Export signalements validés (statut V) depuis PostgreSQL → data_reports.csv",
    "Nettoyage : coords valides, bbox Kinshasa, normalisation degré (faible/modéré/élevé)",
    "Déduplication lat/lon/timestamp (arrondi minute)",
    "Imputation created_at manquant → 2025-01-01 12:00",
    "Split stratifié seed=42 sur données réelles : gold 15 %, val 15 %, test 15 %, reste train réel ; synthétiques uniquement en train",
    "Features : lat, lon, heure, jour semaine, densité 500 m, degré moyen voisins (sans fuite LOO)",
    "StandardScaler + validation croisée 5-fold + sélection modèle (F1 macro)",
]


def generate_eda_plots(
    profile: dict[str, Any],
    output_dir: Path,
    *,
    comparison: dict[str, Any] | None = None,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    plots: dict[str, Path] = {}

    counts = profile.get("class_distribution", {}).get("full") or {}
    if counts:
        path = output_dir / "eda_class_balance.png"
        _plot_class_balance(counts, path)
        plots["class_balance"] = path

    temporal = profile.get("temporal") or {}
    if temporal.get("hour_hist"):
        path = output_dir / "eda_hour_distribution.png"
        _plot_histogram(
            temporal["hour_hist"],
            "Heure de signalement",
            "Nombre",
            path,
            xlabels=[str(h) for h in range(24)],
        )
        plots["hour_distribution"] = path

    if temporal.get("weekday_hist"):
        days = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
        path = output_dir / "eda_weekday_distribution.png"
        _plot_histogram(temporal["weekday_hist"], "Jour de la semaine", "Nombre", path, xlabels=days)
        plots["weekday_distribution"] = path

    locations = profile.get("locations") or {}
    if locations:
        path = output_dir / "eda_top_locations.png"
        _plot_bar_top(locations, "Quartiers les plus signalés", path)
        plots["top_locations"] = path

    descriptions = profile.get("descriptions") or {}
    tokens = descriptions.get("top_tokens") or {}
    if tokens:
        path = output_dir / "eda_top_descriptions.png"
        _plot_bar_top(tokens, "Mots-clés description (top 15)", path, limit=15)
        plots["top_descriptions"] = path

    try:
        root = resolve_prediction_data_dir()
        df, _ = load_cleaned(root)
        path = output_dir / "eda_spatial_scatter.png"
        _plot_spatial_scatter(df, path)
        plots["spatial_scatter"] = path
    except Exception:
        pass

    if comparison:
        path = output_dir / "eda_model_comparison.png"
        _plot_model_comparison(comparison, path)
        plots["model_comparison"] = path

    return plots


def plot_confusion_matrix(
    matrix: list[list[int]],
    labels: list[str],
    output: Path,
    *,
    title: str = "Matrice de confusion",
) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6, 5))
    data = np.array(matrix)
    im = ax.imshow(data, cmap="Blues")
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_yticklabels(labels)
    ax.set_xlabel("Prédit")
    ax.set_ylabel("Réel")
    ax.set_title(title)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            ax.text(j, i, str(data[i, j]), ha="center", va="center", color="black")
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output


def plot_f1_per_class(report: dict, labels: list[str], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    f1_values = [float(report.get(lbl, {}).get("f1-score", 0)) for lbl in labels]
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(labels, f1_values, color=["#22c55e", "#f59e0b", "#ef4444"])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("F1-score")
    ax.set_title("F1 par classe — gold_eval")
    for bar, val in zip(bars, f1_values):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.02, f"{val:.2f}", ha="center")
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output


def plot_cv_comparison(comparison: dict[str, Any], output: Path) -> Path:
    return _plot_model_comparison(comparison, output)


def _plot_class_balance(counts: dict[str, int], output: Path) -> None:
    labels = [CLASS_NAMES_FR[CLASS_NAMES.index(k)] if k in CLASS_NAMES else k for k in counts]
    values = list(counts.values())
    colors = ["#22c55e", "#f59e0b", "#ef4444"]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(labels, values, color=colors[: len(values)])
    ax.set_title("Répartition des classes (degré de danger)")
    ax.set_ylabel("Nombre de signalements")
    for i, v in enumerate(values):
        ax.text(i, v + 0.5, str(v), ha="center")
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)


def _plot_histogram(
    hist: dict[str, int],
    xlabel: str,
    ylabel: str,
    output: Path,
    *,
    xlabels: list[str] | None = None,
) -> None:
    keys = sorted(hist.keys(), key=lambda k: int(k))
    values = [hist[k] for k in keys]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(range(len(values)), values, color="#3b82f6")
    if xlabels and len(xlabels) == len(values):
        ax.set_xticks(range(len(values)))
        ax.set_xticklabels(xlabels, rotation=45 if len(xlabels) > 7 else 0)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)


def _plot_bar_top(data: dict[str, int], title: str, output: Path, *, limit: int = 12) -> None:
    items = sorted(data.items(), key=lambda x: -x[1])[:limit]
    labels = [k[:20] for k, _ in items]
    values = [v for _, v in items]
    fig, ax = plt.subplots(figsize=(8, max(4, len(labels) * 0.35)))
    ax.barh(labels[::-1], values[::-1], color="#6366f1")
    ax.set_title(title)
    ax.set_xlabel("Occurrences")
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)


def _plot_spatial_scatter(df: pd.DataFrame, output: Path) -> None:
    color_map = {"faible": "#22c55e", "modere": "#f59e0b", "eleve": "#ef4444"}
    fig, ax = plt.subplots(figsize=(8, 6))
    for degree, group in df.groupby("degree_report"):
        ax.scatter(
            group["longitude_report"],
            group["latitude_report"],
            c=color_map.get(str(degree), "#64748b"),
            label=str(degree),
            alpha=0.7,
            s=35,
        )
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Carte des signalements par degré de danger")
    ax.legend(title="Degré")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)


def _plot_model_comparison(comparison: dict[str, Any], output: Path) -> None:
    names = list(comparison.keys())
    f1_means = [comparison[n]["f1_macro_mean"] for n in names]
    f1_stds = [comparison[n]["f1_macro_std"] for n in names]
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(names))
    ax.bar(x, f1_means, yerr=f1_stds, capsize=4, color="#0ea5e9", alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=20, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("F1 macro (CV 5-fold)")
    ax.set_title("Comparaison des modèles — validation croisée")
    for i, val in enumerate(f1_means):
        ax.text(i, val + 0.03, f"{val:.3f}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)


def build_eda_summary(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "preprocessing": PREPROCESSING_PIPELINE,
        "features": FEATURE_NAMES,
        "totals": profile.get("splits") or {"full": profile.get("total_clean")},
        "class_distribution": profile.get("class_distribution"),
        "cleaning": profile.get("cleaning"),
        "temporal": profile.get("temporal"),
        "spatial": profile.get("spatial"),
    }
