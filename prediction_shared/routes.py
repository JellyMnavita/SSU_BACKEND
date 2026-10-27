"""Scoring d'itinéraires avec pénalité signalements terrain."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np

from prediction_shared.hazards import enrich_route_sample_points, report_proximity_hazard
from prediction_shared.inference import load_assets, predict_point


def _sample_route_geometry(geometry: list, max_points: int = 48) -> list[tuple[float, float]]:
    if not geometry:
        return []
    if len(geometry) <= max_points:
        sampled = geometry
    else:
        indexes = np.linspace(0, len(geometry) - 1, num=max_points, dtype=int)
        sampled = [geometry[index] for index in indexes]

    normalized: list[tuple[float, float]] = []
    for point in sampled:
        if len(point) < 2:
            continue
        lon, lat = point[0], point[1]
        normalized.append((float(lat), float(lon)))

    last_lon, last_lat = geometry[-1][0], geometry[-1][1]
    last_point = (float(last_lat), float(last_lon))
    if not normalized or normalized[-1] != last_point:
        normalized.append(last_point)
    return normalized


def _effective_point_risk(point: dict[str, Any]) -> float:
    """Réduit le bruit ML quand aucun signalement n'est documenté à proximité."""
    ml_risk = float(point.get("risk_score", 0))
    density = int(point.get("density", 0))
    report_hazard = float(point.get("report_hazard", 0))
    if report_hazard >= 0.45:
        return max(ml_risk, report_hazard)
    if density >= 1:
        return ml_risk
    return ml_risk * 0.35


def _is_high_risk_sample(point: dict[str, Any]) -> bool:
    density = int(point.get("density", 0))
    report_hazard = float(point.get("report_hazard", 0))
    risk_score = float(point.get("risk_score", 0))
    prediction = int(point.get("prediction", 0))
    if report_hazard >= 0.85:
        return True
    if density >= 1 and (prediction >= 2 or risk_score >= 0.55):
        return True
    return prediction >= 2 and risk_score >= 0.82 and density >= 1


def _is_moderate_risk_sample(point: dict[str, Any]) -> bool:
    if _is_high_risk_sample(point):
        return False
    density = int(point.get("density", 0))
    report_hazard = float(point.get("report_hazard", 0))
    risk_score = float(point.get("risk_score", 0))
    prediction = int(point.get("prediction", 0))
    if report_hazard >= 0.45:
        return True
    if density >= 1 and prediction >= 1:
        return True
    return 0.4 <= risk_score < 0.7 and density >= 1


def _route_risk_level(avg_risk_score: float, high_risk_points: int, sampled_points: int) -> str:
    high_risk_ratio = high_risk_points / max(sampled_points, 1)
    if avg_risk_score >= 0.65 or high_risk_ratio >= 0.35:
        return "high"
    if avg_risk_score >= 0.35 or high_risk_ratio >= 0.15:
        return "medium"
    return "low"


def _build_route_justifications(
    *,
    avg_risk_score: float,
    max_risk_score: float,
    high_risk_points: int,
    moderate_risk_points: int,
    sampled_points: int,
    average_density: float,
    report_hazard_max: float,
    report_crossings: int,
) -> list[str]:
    justifications: list[str] = []

    if report_crossings > 0:
        justifications.append(
            f"{report_crossings} signalement(s) validé(s) à moins de 120 m du tracé — "
            "pénalité appliquée même si le modèle ML est optimiste."
        )
    elif report_hazard_max >= 0.45:
        justifications.append(
            "Le trajet longe une zone avec signalements validés à proximité (~500 m)."
        )
    elif high_risk_points == 0:
        justifications.append(
            "Aucun segment fortement risqué ni signalement validé directement sur le tracé."
        )
    else:
        justifications.append(
            f"{high_risk_points} point(s) échantillonnés présentent un risque élevé (modèle)."
        )

    if avg_risk_score < 0.35 and report_hazard_max < 0.45:
        justifications.append(
            "Le trajet reste majoritairement dans des zones à faible exposition."
        )
    elif avg_risk_score < 0.65 and report_hazard_max < 0.75:
        justifications.append(
            "Quelques zones de vigilance ; le score intègre modèle ML + signalements réels."
        )
    else:
        justifications.append(
            "Trajet exposé — évitez si possible (modèle et/ou signalements terrain)."
        )

    if moderate_risk_points:
        justifications.append(
            f"{moderate_risk_points} segment(s) en vigilance modérée."
        )

    if max_risk_score >= 0.8 or report_hazard_max >= 0.9:
        justifications.append(
            "Pic de risque ponctuel (modèle ou passage sur un signalement)."
        )

    return justifications[:4]


def _resolve_travel_mode(route: dict[str, Any]) -> str:
    explicit = route.get("travel_mode")
    if explicit in ("walking", "driving", "cycling"):
        return str(explicit)
    route_id = str(route.get("id") or "")
    if route_id.startswith("driving_"):
        return "driving"
    if route_id.startswith("cycling_"):
        return "cycling"
    return "walking"


def score_routes(payload: dict, *, data_dir=None) -> dict[str, Any]:
    from pathlib import Path

    now = datetime.now()
    hour = payload.get("hour", now.hour)
    day_of_week = payload.get("day_of_week", now.weekday())
    routes = payload["routes"]
    root = Path(data_dir) if data_dir else None
    root_key = str(root) if root else ""
    reports_df, tree, _, _ = load_assets(root_key)

    scored = []
    for index, route in enumerate(routes, start=1):
        geometry = route["geometry"]
        base_samples = _sample_route_geometry(geometry)
        if len(base_samples) < 2:
            raise ValueError("Géométrie de route invalide")

        sample_points = enrich_route_sample_points(
            geometry, reports_df, base_samples=base_samples
        )

        point_scores = []
        report_hazards = []
        report_crossings = 0

        for lat, lon in sample_points:
            ml = predict_point(lat, lon, hour, day_of_week, data_dir=root)
            hazard = report_proximity_hazard(lat, lon, reports_df, tree)
            ml["report_hazard"] = hazard["hazard_score"]
            ml["nearest_report_km"] = hazard["nearest_report_km"]
            point_scores.append(ml)
            report_hazards.append(hazard["hazard_score"])
            if hazard["hazard_score"] >= 0.85:
                report_crossings += 1

        route_risk_scores = [_effective_point_risk(p) for p in point_scores]
        avg_risk = float(np.mean(route_risk_scores))
        max_risk = float(np.max(route_risk_scores))
        max_report_hazard = float(max(report_hazards)) if report_hazards else 0.0
        avg_report_hazard = float(np.mean(report_hazards)) if report_hazards else 0.0

        sampled_count = len(point_scores)
        high_risk_points = sum(1 for p in point_scores if _is_high_risk_sample(p))
        moderate_risk_points = sum(1 for p in point_scores if _is_moderate_risk_sample(p))
        average_density = float(np.mean([p["density"] for p in point_scores]))
        average_model_confidence = float(np.mean([p["confidence"] for p in point_scores]))

        distance_penalty = min(float(route["distance_m"]) / 15000.0, 1.0) * 0.12
        duration_penalty = min(float(route["duration_s"]) / 3600.0, 1.0) * 0.05
        high_risk_penalty = (high_risk_points / max(sampled_count, 1)) * 0.22
        report_penalty = min(0.48, max(max_report_hazard * 0.28, avg_report_hazard * 0.16))
        if report_crossings >= 1:
            report_penalty = min(
                0.58,
                max(report_penalty, 0.18 + min(report_crossings, 5) * 0.03),
            )

        combined_avg = max(avg_risk, avg_report_hazard * 0.75)
        combined_max = max(max_risk, max_report_hazard)

        optimization_cost = min(
            1.0,
            (combined_avg * 0.36)
            + (combined_max * 0.22)
            + high_risk_penalty * 0.85
            + report_penalty
            + distance_penalty
            + duration_penalty,
        )
        safety_score = max(0.0, 1.0 - optimization_cost)
        score_breakdown = {
            "avg_risk_component": round(combined_avg * 0.36, 4),
            "max_risk_component": round(combined_max * 0.22, 4),
            "high_risk_component": round(high_risk_penalty * 0.85, 4),
            "report_penalty": round(report_penalty, 4),
            "distance_penalty": round(distance_penalty, 4),
            "duration_penalty": round(duration_penalty, 4),
            "total_cost": round(optimization_cost, 4),
            "formula": (
                "coût = risque_moy×0,36 + pic_risque×0,22 + segments_risque×0,85 "
                "+ signalements + distance + durée ; sécurité = 1 − coût"
            ),
        }

        scored.append(
            {
                "route_id": route.get("id") or f"route_{index}",
                "travel_mode": _resolve_travel_mode(route),
                "distance_m": float(route["distance_m"]),
                "duration_s": float(route["duration_s"]),
                "geometry": geometry,
                "safety_score": round(safety_score, 4),
                "optimization_cost": round(optimization_cost, 4),
                "score_breakdown": score_breakdown,
                "avg_risk_score": round(combined_avg, 4),
                "max_risk_score": round(combined_max, 4),
                "max_report_hazard": round(max_report_hazard, 4),
                "report_crossings": int(report_crossings),
                "risk_level": _route_risk_level(combined_avg, high_risk_points, sampled_count),
                "high_risk_points": int(high_risk_points),
                "moderate_risk_points": int(moderate_risk_points),
                "sampled_points": int(sampled_count),
                "average_density": round(average_density, 2),
                "average_model_confidence": round(average_model_confidence, 4),
                "justifications": _build_route_justifications(
                    avg_risk_score=combined_avg,
                    max_risk_score=combined_max,
                    high_risk_points=high_risk_points,
                    moderate_risk_points=moderate_risk_points,
                    sampled_points=sampled_count,
                    average_density=average_density,
                    report_hazard_max=max_report_hazard,
                    report_crossings=report_crossings,
                ),
            }
        )

    ranked = sorted(scored, key=lambda r: r["optimization_cost"])
    shortest = min(scored, key=lambda r: r["distance_m"])
    costs = [r["optimization_cost"] for r in scored]
    min_cost = min(costs)
    max_cost = max(costs)
    span = max(max_cost - min_cost, 1e-6)
    for route in scored:
        relative = 1.0 - (route["optimization_cost"] - min_cost) / span
        route["relative_safety_score"] = round(relative, 4)
        absolute_pct = route["safety_score"] * 100
        relative_pct = relative * 100
        route["display_safety_pct"] = round(
            max(absolute_pct, relative_pct * 0.25 + absolute_pct * 0.75),
            1,
        )
    return {
        "origin": payload["origin"],
        "destination": payload["destination"],
        "recommended_route": ranked[0],
        "alternatives": ranked[1:],
        "routes_evaluated": len(ranked),
        "comparison": {
            "shortest_route_id": shortest["route_id"],
            "recommended_is_shortest": ranked[0]["route_id"] == shortest["route_id"],
        },
    }
