"""Ajuste le degré de danger (F/M/E) à partir du NLP, de la vision et des mots-clés."""

from __future__ import annotations

DEGREE_RANK = {"F": 0, "M": 1, "E": 2}
RANK_TO_DEGREE = {0: "F", 1: "M", 2: "E"}

# Type d'incident NLP → degré minimal suggéré
INCIDENT_TO_DEGREE: dict[str, str] = {
    "kidnapping": "E",
    "violence": "E",
    "agression": "M",
    "vol": "M",
    "vandalisme": "M",
    "autre": "F",
}

# Labels vision SSU → degré
VISION_LABEL_TO_DEGREE: dict[str, str] = {
    "arme": "E",
    "incendie": "E",
    "accident": "M",
    "foule": "M",
    "vehicule_suspect": "M",
    "autre": "F",
}

VISION_CONFIDENCE_MIN = 0.20
NLP_HIGH_RISK_TYPES = frozenset({"violence", "kidnapping"})
# Violence/kidnapping : seuil élevé pour éviter les faux positifs (ex. LSTM à 25 %)
NLP_HIGH_RISK_CONFIDENCE_MIN = 0.50
NLP_MEDIUM_CONFIDENCE_MIN = 0.45
NLP_LOW_CONFIDENCE_MIN = 0.35


def _max_degree(*degrees: str | None) -> str:
    best = "F"
    for d in degrees:
        if d and DEGREE_RANK.get(d, 0) > DEGREE_RANK[best]:
            best = d
    return best


def degree_from_nlp(nlp: dict | None) -> tuple[str, list[str]]:
    if not nlp:
        return "F", []
    incident = nlp.get("incident_type") or "autre"
    confidence = float(nlp.get("confidence") or 0)
    suggested = INCIDENT_TO_DEGREE.get(incident, "F")

    reasons = []
    if suggested == "F":
        return "F", reasons

    if confidence < NLP_LOW_CONFIDENCE_MIN:
        return "F", reasons

    if incident in NLP_HIGH_RISK_TYPES and confidence >= NLP_HIGH_RISK_CONFIDENCE_MIN:
        reasons.append(
            f"NLP: {incident} (confiance {confidence:.0%}) → {suggested}"
        )
        return suggested, reasons

    if confidence >= NLP_MEDIUM_CONFIDENCE_MIN and suggested in ("M", "E"):
        reasons.append(
            f"NLP: {incident} (confiance {confidence:.0%}) → {suggested}"
        )
        return suggested, reasons

    if confidence >= NLP_LOW_CONFIDENCE_MIN and suggested == "M":
        reasons.append(
            f"NLP: {incident} (confiance {confidence:.0%}) → M"
        )
        return "M", reasons

    return "F", reasons


def degree_from_vision(vision: dict | None) -> tuple[str, list[str]]:
    if not vision:
        return "F", []

    objects = vision.get("detected_objects") or []
    best = "F"
    reasons: list[str] = []

    for obj in objects:
        label = obj.get("label") or "autre"
        conf = float(obj.get("confidence") or 0)
        if conf < VISION_CONFIDENCE_MIN:
            continue
        suggested = VISION_LABEL_TO_DEGREE.get(label, "F")
        if DEGREE_RANK[suggested] > DEGREE_RANK[best]:
            best = suggested
            reasons.append(f"Vision: {label} ({conf:.0%}) → {suggested}")

    return best, reasons


def degree_from_keywords(description: str) -> tuple[str, list[str]]:
    from .content_filters import keywords_risk, looks_non_security_news

    if not description or looks_non_security_news(description):
        return "F", []
    score, detail = keywords_risk(description)
    if score >= 0.80:
        return "E", [f"{detail} → E"]
    if score >= 0.45:
        return "M", [f"{detail} → M"]
    return "F", []


def compute_ai_recommended_degree(
    description: str,
    nlp: dict | None,
    vision: dict | None,
) -> dict:
    """Calcule le degré recommandé via fusion pondérée NLP + vision + mots-clés."""
    from .fusion import compute_fusion

    fusion = compute_fusion(description, nlp, vision)
    return {
        "ai_recommended_degree": fusion["ai_recommended_degree"],
        "nlp_degree": fusion["nlp_degree"],
        "vision_degree": fusion["vision_degree"],
        "keywords_degree": fusion["keywords_degree"],
        "reasons": fusion["reasons"],
        "fusion": fusion,
    }


def apply_degree_adjustment(report, enrichment: dict) -> dict:
    """
    Met à jour report.degree si l'IA recommande un niveau plus élevé
    que celui déclaré par l'utilisateur (jamais de rétrogradation).
    """
    user_degree = report.degree
    analysis = compute_ai_recommended_degree(
        description=report.description or "",
        nlp=enrichment.get("nlp"),
        vision=enrichment.get("vision"),
    )
    recommended = analysis["ai_recommended_degree"]
    final_degree = _max_degree(user_degree, recommended)
    adjusted = DEGREE_RANK[final_degree] > DEGREE_RANK[user_degree]

    degree_meta = {
        "user_declared": user_degree,
        "ai_recommended": recommended,
        "applied": final_degree,
        "adjusted": adjusted,
        "reasons": analysis["reasons"],
    }

    if adjusted:
        report.user_degree_before_ai = user_degree
        report.ai_recommended_degree = recommended
        report.degree_adjusted_by_ai = True
        report.degree = final_degree
        report.save(
            update_fields=[
                "degree",
                "user_degree_before_ai",
                "ai_recommended_degree",
                "degree_adjusted_by_ai",
            ]
        )
    elif recommended != "F":
        report.ai_recommended_degree = recommended
        report.degree_adjusted_by_ai = False
        report.save(update_fields=["ai_recommended_degree", "degree_adjusted_by_ai"])

    return degree_meta
