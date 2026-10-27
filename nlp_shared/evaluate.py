"""Évaluation NLP — gold, règles, filtres anodins."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

from nlp_shared.lexicon_data import INCIDENT_TYPES
from nlp_shared.training.dataset import resolve_nlp_data_dir
from nlp_shared.training.metrics import compute_metrics


def _load_json(path: Path) -> list | dict | None:
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _classify_via_api(text: str, base_url: str) -> dict:
    url = base_url.rstrip("/") + "/classify-text"
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_classifier(api_url: str | None) -> Callable[[str], dict]:
    if api_url:
        return lambda text: _classify_via_api(text, api_url)

    import sys

    root = Path(__file__).resolve().parents[1]
    nlp_app = root / "ai_services" / "nlp_service"
    for path in (root, nlp_app):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

    models_dir = os.environ.get("MODELS_DIR")
    if models_dir:
        from app.config import settings

        settings.models_dir = models_dir

    from app.classifier import classify_text

    return classify_text


def evaluate_rules_cases(data_dir: Path | None = None) -> dict:
    root = data_dir or resolve_nlp_data_dir()
    from nlp_shared.rules import match_rule

    cases = _load_json(root / "rules_eval.json") or []
    ok = 0
    failures: list[str] = []
    for case in cases:
        text = case["text"]
        matched = match_rule(text)
        expect_label = case.get("expect_label")
        min_conf = float(case.get("min_confidence", 0.0))
        if expect_label is None:
            if matched is None:
                ok += 1
            else:
                failures.append(f"{case.get('id')}: aucune règle attendue")
            continue
        if matched is None:
            failures.append(f"{case.get('id')}: règle {expect_label} attendue")
            continue
        label, conf, _ = matched
        if label == expect_label and conf >= min_conf:
            ok += 1
        else:
            failures.append(f"{case.get('id')}: attendu {expect_label}, reçu {label}")
    return {"ok": ok, "total": len(cases), "accuracy": ok / len(cases) if cases else 0, "failures": failures[:10]}


def evaluate_benign_cases(data_dir: Path | None = None) -> dict:
    root = data_dir or resolve_nlp_data_dir()
    from nlp_shared.filters import is_benign_content

    cases = _load_json(root / "benign_eval.json") or []
    ok = 0
    failures: list[str] = []
    for case in cases:
        text = case["text"]
        expect = bool(case["expect_benign"])
        got = is_benign_content(text)
        if got == expect:
            ok += 1
        else:
            failures.append(case.get("id", "?"))
    return {"ok": ok, "total": len(cases), "accuracy": ok / len(cases) if cases else 0, "failures": failures[:10]}


def run_gold_evaluation(
    data_dir: Path | None = None,
    *,
    api_url: str | None = None,
    models_dir: Path | None = None,
) -> dict:
    root = data_dir or resolve_nlp_data_dir()
    out_dir = root / "models"
    out_dir.mkdir(parents=True, exist_ok=True)

    gold = _load_json(root / "gold_eval.json") or []
    if not gold:
        return {"status": "error", "message": "gold_eval.json vide ou introuvable"}

    if models_dir:
        os.environ["MODELS_DIR"] = str(models_dir)

    classify = _get_classifier(api_url)
    y_true: list[str] = []
    y_pred: list[str] = []
    model_used: dict[str, int] = {}
    errors: list[str] = []

    for case in gold:
        text = (case.get("text") or "").strip()
        label = (case.get("label") or "").strip()
        if not text or label not in INCIDENT_TYPES:
            continue
        try:
            result = classify(text)
        except (urllib.error.URLError, OSError, ImportError) as exc:
            errors.append(str(exc))
            break
        pred = result.get("incident_type") or "autre"
        used = result.get("model_used") or "unknown"
        model_used[used] = model_used.get(used, 0) + 1
        y_true.append(label)
        y_pred.append(pred)

    if errors:
        return {"status": "error", "message": errors[0]}

    metrics = compute_metrics(y_true, y_pred, INCIDENT_TYPES)
    cm_labels = list(INCIDENT_TYPES)
    from sklearn.metrics import confusion_matrix

    payload = {
        "status": "ok",
        "samples": len(y_true),
        "metrics": {
            **metrics,
            "confusion_matrix": confusion_matrix(y_true, y_pred, labels=cm_labels).tolist(),
            "labels_order": cm_labels,
            "selection_score": metrics["f1_macro"],
        },
        "model_used_distribution": model_used,
    }

    out_path = out_dir / "gold_eval_results.json"
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return {**payload, "path": str(out_path)}


def fetch_training_registry(api_url: str | None = None, data_dir: Path | None = None) -> dict:
    """Charge active_model.json local ou via GET /health du microservice."""
    root = data_dir or resolve_nlp_data_dir()
    local = root / "models" / "active_model.json"
    if local.is_file():
        return json.loads(local.read_text(encoding="utf-8"))

    if not api_url:
        return {}

    try:
        url = api_url.rstrip("/") + "/health"
        with urllib.request.urlopen(url, timeout=15) as resp:
            health = json.loads(resp.read().decode("utf-8"))
        return {
            "primary_ml": health.get("primary_ml"),
            "ml_priority": health.get("ml_priority"),
            "trained_at": health.get("trained_at"),
            "data_source": health.get("data_source"),
            "comparison": health.get("comparison"),
            "selection_reason": health.get("selection_reason"),
        }
    except (urllib.error.URLError, OSError):
        return {}
