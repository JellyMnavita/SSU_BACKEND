"""Entraînement et évaluation des modèles NLP."""

from nlp_shared.training.dataset import load_corpus_splits
from nlp_shared.training.metrics import compute_metrics, metrics_summary

__all__ = ["compute_metrics", "load_corpus_splits", "metrics_summary"]
