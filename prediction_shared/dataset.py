"""Chargement, nettoyage et splits du dataset de prédiction spatiale."""

from __future__ import annotations

import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from prediction_shared.labels import (
    CLASS_NAMES,
    DEGREE_LABEL_MAP,
    KINSHASA_LAT_MAX,
    KINSHASA_LAT_MIN,
    KINSHASA_LON_MAX,
    KINSHASA_LON_MIN,
)

CSV_COLUMNS = [
    "latitude_report",
    "longitude_report",
    "location_report",
    "degree_report",
    "description_report",
    "created_at",
]

# Métadonnée exportée : "real" | "synthetic" (non utilisée comme feature ML)
SOURCE_COLUMN = "source_report"

GOLD_RATIO = 0.15
VAL_RATIO = 0.15
TEST_RATIO = 0.15
RANDOM_SEED = 42


def resolve_prediction_data_dir() -> Path:
    """Dossier ``prediction/`` des CSV et des poids.

    Deux dispositions :
    - monorepo : ``<racine>/prediction_shared`` à côté de ``<racine>/ssu_backend/prediction``
    - dépôt backend : ``prediction_shared`` à côté de ``prediction/``
    """
    if env := os.environ.get("PREDICTION_DATA_DIR"):
        return Path(env)
    container = Path(__file__).resolve().parents[1]
    monorepo = container / "ssu_backend" / "prediction"
    if (container / "ssu_backend").is_dir():
        return monorepo
    return container / "prediction"


def raw_csv_path(data_dir: Path | None = None) -> Path:
    root = data_dir or resolve_prediction_data_dir()
    return root / "data" / "data_reports.csv"


def splits_dir(data_dir: Path | None = None) -> Path:
    root = data_dir or resolve_prediction_data_dir()
    return root / "splits"


def gold_eval_dir(data_dir: Path | None = None) -> Path:
    root = data_dir or resolve_prediction_data_dir()
    return root / "gold_eval"


def models_dir(data_dir: Path | None = None) -> Path:
    root = data_dir or resolve_prediction_data_dir()
    return root / "models"


def production_model_dir(data_dir: Path | None = None) -> Path:
    root = data_dir or resolve_prediction_data_dir()
    return root / "model"


@dataclass
class CleaningReport:
    rows_read: int = 0
    rows_kept: int = 0
    removed_invalid_coords: int = 0
    removed_out_of_bbox: int = 0
    removed_invalid_degree: int = 0
    removed_duplicates: int = 0
    filled_created_at: int = 0
    normalized_degree: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "rows_read": self.rows_read,
            "rows_kept": self.rows_kept,
            "removed_invalid_coords": self.removed_invalid_coords,
            "removed_out_of_bbox": self.removed_out_of_bbox,
            "removed_invalid_degree": self.removed_invalid_degree,
            "removed_duplicates": self.removed_duplicates,
            "filled_created_at": self.filled_created_at,
            "normalized_degree": self.normalized_degree,
        }


def _normalize_degree(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    text = str(value).strip().lower()
    if text in DEGREE_LABEL_MAP:
        return CLASS_NAMES[DEGREE_LABEL_MAP[text]]
    return None


def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, CleaningReport]:
    """Nettoyage : coords valides, bbox Kinshasa, degré normalisé, déduplication."""
    report = CleaningReport(rows_read=len(df))
    working = df.copy()

    for col in CSV_COLUMNS:
        if col not in working.columns:
            working[col] = np.nan

    working["latitude_report"] = pd.to_numeric(working["latitude_report"], errors="coerce")
    working["longitude_report"] = pd.to_numeric(working["longitude_report"], errors="coerce")

    invalid_coords = working["latitude_report"].isna() | working["longitude_report"].isna()
    report.removed_invalid_coords = int(invalid_coords.sum())
    working = working.loc[~invalid_coords].copy()

    out_of_bbox = (
        (working["latitude_report"] < KINSHASA_LAT_MIN)
        | (working["latitude_report"] > KINSHASA_LAT_MAX)
        | (working["longitude_report"] < KINSHASA_LON_MIN)
        | (working["longitude_report"] > KINSHASA_LON_MAX)
    )
    report.removed_out_of_bbox = int(out_of_bbox.sum())
    working = working.loc[~out_of_bbox].copy()

    normalized: list[str | None] = []
    for raw in working["degree_report"]:
        norm = _normalize_degree(raw)
        if norm is None:
            normalized.append(None)
        else:
            normalized.append(norm)
            if str(raw).strip().lower() not in DEGREE_LABEL_MAP:
                report.normalized_degree += 1
    working["degree_report"] = normalized

    invalid_degree = working["degree_report"].isna()
    report.removed_invalid_degree = int(invalid_degree.sum())
    working = working.loc[~invalid_degree].copy()

    missing_ts = working["created_at"].isna() | (
        working["created_at"].astype(str).str.strip() == ""
    )
    report.filled_created_at = int(missing_ts.sum())
    working.loc[missing_ts, "created_at"] = "2025-01-01 12:00:00"

    working["_dedupe_key"] = (
        working["latitude_report"].round(5).astype(str)
        + "|"
        + working["longitude_report"].round(5).astype(str)
        + "|"
        + working["created_at"].astype(str).str.slice(0, 16)
    )
    before = len(working)
    working = working.drop_duplicates(subset=["_dedupe_key"], keep="first")
    report.removed_duplicates = before - len(working)
    working = working.drop(columns=["_dedupe_key"])

    working = working.reset_index(drop=True)
    report.rows_kept = len(working)
    return working, report


def load_raw_csv(data_dir: Path | None = None) -> pd.DataFrame:
    path = raw_csv_path(data_dir)
    if not path.is_file():
        raise FileNotFoundError(f"Dataset introuvable : {path}")
    return pd.read_csv(path)


def load_cleaned(data_dir: Path | None = None) -> tuple[pd.DataFrame, CleaningReport]:
    df = load_raw_csv(data_dir)
    if df.empty:
        raise ValueError("Dataset vide — aucun signalement pour l'entraînement.")
    return clean_dataframe(df)


def load_split(name: str, data_dir: Path | None = None) -> pd.DataFrame:
    path = splits_dir(data_dir) / f"{name}.csv"
    if not path.is_file():
        return pd.DataFrame(columns=CSV_COLUMNS)
    return pd.read_csv(path)


def load_gold_eval(data_dir: Path | None = None) -> pd.DataFrame:
    path = gold_eval_dir(data_dir) / "gold_eval.csv"
    if not path.is_file():
        return pd.DataFrame(columns=CSV_COLUMNS)
    return pd.read_csv(path)


def _is_synthetic_mask(df: pd.DataFrame) -> pd.Series:
    if SOURCE_COLUMN not in df.columns:
        return pd.Series(False, index=df.index)
    return (
        df[SOURCE_COLUMN].fillna("real").astype(str).str.strip().str.lower() == "synthetic"
    )


def _stratified_split_indices(
    labels: list[int],
    *,
    ratio: float,
    rng: random.Random,
) -> set[int]:
    by_class: dict[int, list[int]] = {}
    for idx, label in enumerate(labels):
        by_class.setdefault(label, []).append(idx)

    selected: set[int] = set()
    for indices in by_class.values():
        rng.shuffle(indices)
        n = max(1, int(round(len(indices) * ratio))) if len(indices) >= 3 else min(1, len(indices))
        selected.update(indices[:n])
    return selected


def build_splits(
    data_dir: Path | None = None,
    *,
    seed: int = RANDOM_SEED,
    write: bool = True,
) -> dict[str, Any]:
    """
    Construit gold_eval + train/val/test stratifiés par degré de danger.

    Politique :
    - gold / val / test : signalements réels uniquement (jamais synthétiques)
    - train : reste des réels + l'intégralité des synthétiques
    """
    df, cleaning = load_cleaned(data_dir)
    synthetic_mask = _is_synthetic_mask(df)
    real_df = df.loc[~synthetic_mask].reset_index(drop=True)
    synthetic_df = df.loc[synthetic_mask].reset_index(drop=True)

    if real_df.empty:
        raise ValueError(
            "Aucun signalement réel dans le dataset — impossible de construire un gold_eval honnête."
        )

    label_ids = [DEGREE_LABEL_MAP[d] for d in real_df["degree_report"]]

    rng = random.Random(seed)
    gold_idx = _stratified_split_indices(label_ids, ratio=GOLD_RATIO, rng=rng)
    remaining_idx = [i for i in range(len(real_df)) if i not in gold_idx]

    remaining_labels = [label_ids[i] for i in remaining_idx]
    val_idx_rel = _stratified_split_indices(remaining_labels, ratio=VAL_RATIO, rng=rng)
    val_idx = {remaining_idx[i] for i in val_idx_rel}

    pool = [i for i in remaining_idx if i not in val_idx]
    pool_labels = [label_ids[i] for i in pool]
    test_idx_rel = _stratified_split_indices(pool_labels, ratio=TEST_RATIO, rng=rng)
    test_idx = {pool[i] for i in test_idx_rel}
    train_idx = [i for i in pool if i not in test_idx]

    gold_df = real_df.iloc[sorted(gold_idx)].reset_index(drop=True)
    real_train_df = real_df.iloc[sorted(train_idx)].reset_index(drop=True)
    val_df = real_df.iloc[sorted(val_idx)].reset_index(drop=True)
    test_df = real_df.iloc[sorted(test_idx)].reset_index(drop=True)

    if synthetic_df.empty:
        train_df = real_train_df
    else:
        train_df = pd.concat([real_train_df, synthetic_df], ignore_index=True)
        train_df = train_df.sample(frac=1, random_state=seed).reset_index(drop=True)

    root = data_dir or resolve_prediction_data_dir()
    if write:
        gold_eval_dir(root).mkdir(parents=True, exist_ok=True)
        splits_dir(root).mkdir(parents=True, exist_ok=True)
        gold_df.to_csv(gold_eval_dir(root) / "gold_eval.csv", index=False)
        train_df.to_csv(splits_dir(root) / "train.csv", index=False)
        val_df.to_csv(splits_dir(root) / "val.csv", index=False)
        test_df.to_csv(splits_dir(root) / "test.csv", index=False)

    def _class_counts(frame: pd.DataFrame) -> dict[str, int]:
        counts = {name: 0 for name in CLASS_NAMES}
        for degree in frame["degree_report"]:
            counts[str(degree)] = counts.get(str(degree), 0) + 1
        return counts

    profile = {
        "total_clean": len(df),
        "cleaning": cleaning.to_dict(),
        "split_policy": {
            "gold_real_only": True,
            "val_test_real_only": True,
            "synthetic_train_only": True,
            "real_total": len(real_df),
            "synthetic_total": len(synthetic_df),
            "train_real": len(real_train_df),
            "train_synthetic": len(synthetic_df),
        },
        "splits": {
            "gold": len(gold_df),
            "train": len(train_df),
            "val": len(val_df),
            "test": len(test_df),
        },
        "class_distribution": {
            "full": _class_counts(df),
            "real": _class_counts(real_df),
            "synthetic": _class_counts(synthetic_df),
            "train": _class_counts(train_df),
            "val": _class_counts(val_df),
            "test": _class_counts(test_df),
            "gold": _class_counts(gold_df),
        },
        "seed": seed,
    }
    return {
        "profile": profile,
        "full": df,
        "gold": gold_df,
        "train": train_df,
        "val": val_df,
        "test": test_df,
    }


def build_dataset_profile(data_dir: Path | None = None) -> dict[str, Any]:
    """Profil dataset pour EDA et rapport (reconstruit splits si absents)."""
    root = data_dir or resolve_prediction_data_dir()
    train = load_split("train", root)
    if train.empty:
        result = build_splits(root, write=True)
        profile = result["profile"]
        df = result["full"]
    else:
        df, cleaning = load_cleaned(root)
        profile = {
            "total_clean": len(df),
            "cleaning": cleaning.to_dict(),
            "splits": {
                "gold": len(load_gold_eval(root)),
                "train": len(load_split("train", root)),
                "val": len(load_split("val", root)),
                "test": len(load_split("test", root)),
            },
        }
        counts = {name: 0 for name in CLASS_NAMES}
        for degree in df["degree_report"]:
            counts[str(degree)] = counts.get(str(degree), 0) + 1
        profile["class_distribution"] = {"full": counts}

    df, _ = load_cleaned(root)
    profile["temporal"] = _temporal_stats(df)
    profile["spatial"] = _spatial_stats(df)
    profile["locations"] = _location_stats(df)
    profile["descriptions"] = _description_stats(df)
    return profile


def _temporal_stats(df: pd.DataFrame) -> dict[str, Any]:
    hours: list[int] = []
    weekdays: list[int] = []
    months: list[int] = []
    for ts in df["created_at"]:
        parsed = pd.to_datetime(str(ts), errors="coerce")
        if pd.isna(parsed):
            continue
        hours.append(int(parsed.hour))
        weekdays.append(int(parsed.weekday()))
        months.append(int(parsed.month))

    return {
        "hour_hist": _histogram(hours, bins=24),
        "weekday_hist": _histogram(weekdays, bins=7),
        "month_hist": _histogram(months, bins=12),
        "date_min": str(df["created_at"].min()) if len(df) else None,
        "date_max": str(df["created_at"].max()) if len(df) else None,
    }


def _spatial_stats(df: pd.DataFrame) -> dict[str, Any]:
    lats = df["latitude_report"].astype(float)
    lons = df["longitude_report"].astype(float)
    return {
        "lat_min": float(lats.min()) if len(df) else None,
        "lat_max": float(lats.max()) if len(df) else None,
        "lon_min": float(lons.min()) if len(df) else None,
        "lon_max": float(lons.max()) if len(df) else None,
        "centroid_lat": float(lats.mean()) if len(df) else None,
        "centroid_lon": float(lons.mean()) if len(df) else None,
    }


def _location_stats(df: pd.DataFrame) -> dict[str, int]:
    counts: dict[str, int] = {}
    for loc in df["location_report"].fillna("Inconnu").astype(str):
        key = loc.strip() or "Inconnu"
        counts[key] = counts.get(key, 0) + 1
    top = sorted(counts.items(), key=lambda x: -x[1])[:15]
    return dict(top)


def _description_stats(df: pd.DataFrame) -> dict[str, Any]:
    texts = df["description_report"].fillna("").astype(str).str.strip().str.lower()
    tokens: dict[str, int] = {}
    for text in texts:
        if not text:
            continue
        for word in text.replace("_", " ").split():
            if len(word) >= 3:
                tokens[word] = tokens.get(word, 0) + 1
    top = sorted(tokens.items(), key=lambda x: -x[1])[:20]
    return {"top_tokens": dict(top), "empty_descriptions": int((texts == "").sum())}


def _histogram(values: list[int], bins: int) -> dict[str, int]:
    hist = {str(i): 0 for i in range(bins)}
    for value in values:
        if 0 <= value < bins:
            hist[str(value)] = hist.get(str(value), 0) + 1
    return hist
