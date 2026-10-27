"""Chargement des splits corpus NLP."""

from __future__ import annotations

import os
from pathlib import Path

from nlp_shared.corpus_utils import CorpusRow, load_csv_corpus


def resolve_nlp_data_dir() -> Path:
    """Corpus NLP : ``nlp_data/`` à côté du paquet, ou un cran au-dessus."""
    if env := os.environ.get("NLP_DATA_DIR"):
        return Path(env)
    container = Path(__file__).resolve().parents[2]
    local = container / "nlp_data"
    if local.exists():
        return local
    parent = container.parent / "nlp_data"
    if parent.exists():
        return parent
    return local


def load_corpus_splits(
    data_dir: Path | None = None,
) -> tuple[list[CorpusRow], list[CorpusRow], list[CorpusRow]] | None:
    root = data_dir or resolve_nlp_data_dir()
    train = load_csv_corpus(root / "train.csv")
    val = load_csv_corpus(root / "val.csv")
    test = load_csv_corpus(root / "test.csv")
    if len(train) < 20:
        return None
    return train, val, test


def rows_to_xy(rows: list[CorpusRow]) -> tuple[list[str], list[str]]:
    return [row.text for row in rows], [row.label for row in rows]
