"""
Fusion pondérée NLP + Vision → score global, degré et modération.

Le lexique sécurité est intégré au service NLP (règles prioritaires) ;
il n'y a plus de couche mots-clés séparée dans le score fusionné.
"""

from __future__ import annotations

from .content_filters import looks_benign, looks_non_security_news, has_local_incident_markers
from .degree_adjustment import _max_degree

W_NLP = 0.62
W_VISION = 0.38

INCIDENT_SEVERITY: dict[str, float] = {
    "kidnapping": 1.0,
    "violence": 0.95,
    "agression": 0.70,
    "vol": 0.55,
    "vandalisme": 0.50,
    "autre": 0.10,
}

VISION_SEVERITY: dict[str, float] = {
    "arme": 1.0,
    "incendie": 0.95,
    "accident": 0.60,
    "foule": 0.50,
    "vehicule_suspect": 0.45,
    "autre": 0.08,
}

VISION_MIN_CONF = 0.20
VISION_AUTRE_MIN = 0.25


def _looks_benign(description: str) -> bool:
    return looks_benign(description)


def _nlp_is_rule_match(nlp: dict | None) -> bool:
    return bool(nlp and nlp.get("model_used") == "rules")


def _nlp_risk(nlp: dict | None, description: str = "") -> tuple[float, str]:
    if not nlp:
        return 0.0, ""
    if nlp.get("model_used") == "institutional_filter":
        return 0.05, "NLP : actualité institutionnelle / hors incident local"
    if nlp.get("model_used") == "scraped_news_filter":
        return 0.06, "NLP : actualité scrapée sans incident urbain local signalé"
    if nlp.get("model_used") == "benign_filter":
        return 0.05, "NLP : contenu anodin détecté"

    if looks_non_security_news(description):
        return 0.08, "NLP : actualité institutionnelle / hors incident local"

    incident = nlp.get("incident_type") or "autre"
    conf = float(nlp.get("confidence") or 0)
    base = INCIDENT_SEVERITY.get(incident, 0.10)
    model_used = nlp.get("model_used") or ""

    original = nlp.get("low_confidence_original")
    if original and incident == "autre":
        return min(0.15, conf * 0.3), f"NLP initial peu fiable ({original} {conf:.0%})"

    score = base * conf
    # Règles lexique (ex-bandit, voyou…) : confiance pleine, pas de pénalité.
    if model_used == "rules":
        detail = f"NLP (lexique) : {incident} ({conf:.0%}) → risque {score:.0%}"
        return round(score, 4), detail

    if incident in {"violence", "kidnapping"} and conf < 0.40:
        score *= 0.35

    detail = f"NLP : {incident} ({conf:.0%}) → risque {score:.0%}"
    return round(score, 4), detail


def _vision_risk(vision: dict | None) -> tuple[float, str]:
    if not vision:
        return 0.0, ""

    best_score = 0.0
    best_detail = ""
    for obj in vision.get("detected_objects") or []:
        label = obj.get("label") or "autre"
        conf = float(obj.get("confidence") or 0)
        if conf < VISION_MIN_CONF:
            continue
        if label == "autre" and conf < VISION_AUTRE_MIN:
            continue
        sev = VISION_SEVERITY.get(label, 0.08)
        score = sev * conf
        if score > best_score:
            best_score = score
            best_detail = f"Vision : {label} ({conf:.0%}) → risque {score:.0%}"
    return round(best_score, 4), best_detail


def _score_to_degree(score: float) -> str:
    if score >= 0.65:
        return "E"
    if score >= 0.35:
        return "M"
    return "F"


def compute_fusion(
    description: str,
    nlp: dict | None,
    vision: dict | None,
) -> dict:
    """Agrège NLP (texte + lexique) et vision en un score de risque global [0, 1]."""
    nlp_score, nlp_detail = _nlp_risk(nlp, description)
    vis_score, vis_detail = _vision_risk(vision)

    parts: list[tuple[float, float, str]] = []
    if nlp is not None:
        parts.append((W_NLP, nlp_score, nlp_detail))
    if vision is not None:
        parts.append((W_VISION, vis_score, vis_detail))

    weight_sum = sum(w for w, _, _ in parts)
    fusion_score = sum(w * s for w, s, _ in parts) / weight_sum if weight_sum else 0.0

    active_high = sum(1 for _, s, _ in parts if s >= 0.35)
    if active_high >= 2:
        fusion_score = min(0.98, fusion_score * 1.12)
    elif active_high == 0 and fusion_score < 0.2:
        fusion_score *= 0.85

    fusion_score = round(min(0.98, fusion_score), 4)
    recommended_degree = _score_to_degree(fusion_score)

    nlp_deg = _score_to_degree(nlp_score) if nlp_score else "F"
    vis_deg = _score_to_degree(vis_score) if vis_score else "F"
    recommended_degree = _max_degree(recommended_degree, nlp_deg, vis_deg)

    reasons = [d for _, _, d in parts if d]
    fusion_confidence = round(
        min(0.98, fusion_score * (1.05 if active_high >= 2 else 1.0)),
        4,
    )

    return {
        "fusion_score": fusion_score,
        "fusion_confidence": fusion_confidence,
        "ai_recommended_degree": recommended_degree,
        "nlp_degree": nlp_deg,
        "vision_degree": vis_deg,
        "keywords_degree": nlp_deg if _nlp_is_rule_match(nlp) else "F",
        "active_signals": active_high,
        "reasons": reasons,
        "breakdown": {
            "nlp": {
                "score": nlp_score,
                "weight": W_NLP,
                "contribution": round(W_NLP * nlp_score, 4),
                "detail": nlp_detail,
            },
            "vision": {
                "score": vis_score,
                "weight": W_VISION,
                "contribution": round(W_VISION * vis_score, 4),
                "detail": vis_detail,
            },
            "keywords": {
                "score": 0.0,
                "weight": 0.0,
                "contribution": 0.0,
                "detail": "Intégré au NLP (lexique)",
            },
        },
    }


def moderation_from_fusion(
    description: str,
    enrichment: dict,
    fusion: dict,
    *,
    report_source: str = "",
    reject_settings: dict | None = None,
) -> dict:
    """Décision V / R / P à partir du score fusionné."""
    settings = reject_settings or {}
    reject_enabled = settings.get("auto_reject_enabled", True)
    reject_citizens = settings.get("auto_reject_citizen_reports", False)
    reject_threshold = float(settings.get("auto_reject_score_threshold", 0.15))

    nlp = enrichment.get("nlp") or {}
    errors = enrichment.get("errors") or []
    score = fusion["fusion_score"]
    conf = fusion["fusion_confidence"]
    degree = fusion["ai_recommended_degree"]
    reasons = list(fusion.get("reasons") or [])
    is_scraped_news = report_source == "S"
    is_sos = report_source == "O"
    is_citizen_source = report_source in ("C", "U", "W", "Q")

    if is_sos:
        return {
            "recommendation": "V",
            "confidence": 1.0,
            "reasons": [
                "Alerte SOS — validation automatique système (hors modération IA classique).",
            ],
        }

    if enrichment.get("skipped"):
        return {
            "recommendation": "P",
            "confidence": 0.0,
            "reasons": ["Analyse IA désactivée — revue manuelle requise."],
        }

    vis_score, _ = _vision_risk(enrichment.get("vision"))
    nlp_conf = float(nlp.get("confidence") or 0)
    strong_non_benign = (
        vis_score >= 0.50
        or (_nlp_is_rule_match(nlp) and nlp_conf >= 0.72)
        or has_local_incident_markers(description)
    )

    if is_scraped_news and not has_local_incident_markers(description):
        return {
            "recommendation": "R",
            "confidence": 0.86,
            "reasons": [
                "Actualité scrapée sans vocabulaire d'incident urbain local.",
                f"Score de risque global : {score:.0%}.",
            ],
        }

    if looks_non_security_news(description):
        return {
            "recommendation": "R",
            "confidence": 0.88,
            "reasons": [
                "Article d'actualité générale (institutionnel, politique ou hors incident urbain Kinshasa).",
                f"Score de risque global : {score:.0%}.",
            ],
        }

    if (nlp.get("model_used") == "benign_filter" or _looks_benign(description)) and not strong_non_benign:
        return {
            "recommendation": "R",
            "confidence": 0.85,
            "reasons": [
                "Contenu anodin ou non pertinent pour un signalement de sécurité.",
                f"Score de risque global : {score:.0%}.",
            ],
        }

    if len(description) < 8 and not enrichment.get("vision"):
        return {
            "recommendation": "R",
            "confidence": 0.75,
            "reasons": ["Description trop courte et aucune analyse visuelle."],
        }

    if score < reject_threshold and degree == "F":
        if not reject_enabled:
            return {
                "recommendation": "P",
                "confidence": max(conf, 0.35),
                "reasons": [
                    "Auto-rejet désactivé — revue manuelle malgré un score IA bas.",
                    *reasons,
                ],
            }
        if is_citizen_source and not reject_citizens:
            return {
                "recommendation": "P",
                "confidence": max(conf, 0.35),
                "reasons": [
                    "Signalement citoyen — auto-rejet désactivé pour cette source.",
                    *reasons,
                ],
            }
        return {
            "recommendation": "R",
            "confidence": max(0.7, 1.0 - score),
            "reasons": [
                f"Score de risque global très faible ({score:.0%}) — signalement probablement non pertinent.",
                *reasons,
            ],
        }

    if score >= 0.68 and degree == "E":
        if is_scraped_news and vis_score < 0.35 and not _nlp_is_rule_match(nlp):
            return {
                "recommendation": "P",
                "confidence": conf,
                "reasons": [
                    "Actualité scrapée : risque NLP seul insuffisant pour validation automatique.",
                    *reasons,
                ],
            }
        return {
            "recommendation": "V",
            "confidence": conf,
            "reasons": [
                f"Risque élevé confirmé (score fusion {score:.0%}).",
                *reasons,
            ],
        }

    if score >= 0.52 and degree in ("M", "E") and fusion.get("active_signals", 0) >= 1:
        if is_scraped_news and (score < 0.62 or vis_score < 0.25):
            return {
                "recommendation": "P",
                "confidence": conf,
                "reasons": [
                    "Actualité scrapée : revue manuelle recommandée.",
                    *reasons,
                ],
            }
        return {
            "recommendation": "V",
            "confidence": conf,
            "reasons": [
                f"Incident crédible (score fusion {score:.0%}, degré {degree}).",
                *reasons,
            ],
        }

    if len(errors) >= 2 and score < 0.25:
        return {
            "recommendation": "P",
            "confidence": 0.4,
            "reasons": [
                "Analyse partielle — services IA en échec.",
                *[e.get("detail", "") for e in errors if e.get("detail")],
            ],
        }

    return {
        "recommendation": "P",
        "confidence": max(conf, 0.28),
        "reasons": reasons
        or [
            f"Score fusion {score:.0%} — revue manuelle recommandée (degré {degree})."
        ],
    }
