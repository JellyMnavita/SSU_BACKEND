"""Utilitaires corpus NLP (normalisation, fusion, split)."""

from __future__ import annotations

import csv
import hashlib
import random
import re
from dataclasses import dataclass
from pathlib import Path

from nlp_shared.lexicon_data import INCIDENT_TYPES, SEED_SAMPLES

VALID_LABELS = frozenset(INCIDENT_TYPES)


@dataclass(frozen=True)
class CorpusRow:
    text: str
    label: str
    source: str

    def key(self) -> str:
        normalized = normalize_text(self.text)
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
        return f"{digest}:{self.label}"


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def load_csv_corpus(path: Path) -> list[CorpusRow]:
    if not path.exists():
        return []
    rows: list[CorpusRow] = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            text = normalize_text(row.get("text", ""))
            label = (row.get("label") or "").strip().lower()
            source = (row.get("source") or "unknown").strip()
            if len(text) < 10 or label not in VALID_LABELS:
                continue
            rows.append(CorpusRow(text=text, label=label, source=source))
    return rows


def seed_corpus_rows() -> list[CorpusRow]:
    return [
        CorpusRow(text=normalize_text(text), label=label, source="seed")
        for text, label in SEED_SAMPLES
        if len(normalize_text(text)) >= 10
    ]


def dedupe_rows(rows: list[CorpusRow]) -> list[CorpusRow]:
    seen: set[str] = set()
    out: list[CorpusRow] = []
    for row in rows:
        key = row.key()
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def merge_rows(*groups: list[CorpusRow]) -> list[CorpusRow]:
    return dedupe_rows([row for group in groups for row in group])


def stratified_split(
    rows: list[CorpusRow],
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    seed: int = 42,
) -> tuple[list[CorpusRow], list[CorpusRow], list[CorpusRow]]:
    by_label: dict[str, list[CorpusRow]] = {label: [] for label in INCIDENT_TYPES}
    for row in rows:
        by_label.setdefault(row.label, []).append(row)

    train: list[CorpusRow] = []
    val: list[CorpusRow] = []
    test: list[CorpusRow] = []
    rng = random.Random(seed)

    for label, label_rows in by_label.items():
        if not label_rows:
            continue
        bucket = list(label_rows)
        rng.shuffle(bucket)
        n = len(bucket)
        if n == 1:
            train.extend(bucket)
            continue
        n_train = max(1, int(n * train_ratio))
        n_val = max(0, int(n * val_ratio))
        if n_train + n_val >= n:
            n_val = 1 if n > 2 else 0
            n_train = n - n_val - (1 if n - n_val > n_train else 0)
        n_test = n - n_train - n_val
        if n_test == 0 and n_val > 0:
            n_val -= 1
            n_test = 1
        train.extend(bucket[:n_train])
        val.extend(bucket[n_train : n_train + n_val])
        test.extend(bucket[n_train + n_val :])

    return train, val, test


def write_corpus_csv(path: Path, rows: list[CorpusRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "label", "source"])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {"text": row.text, "label": row.label, "source": row.source}
            )


def label_counts(rows: list[CorpusRow]) -> dict[str, int]:
    counts = {label: 0 for label in INCIDENT_TYPES}
    for row in rows:
        counts[row.label] = counts.get(row.label, 0) + 1
    return counts
