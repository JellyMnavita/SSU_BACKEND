"""Utilitaires carte — agrégation communes (Django DB) ; ML délégué au microservice."""

from __future__ import annotations

from typing import Any

import numpy as np
from django.db.models import Q

from prediction_shared.grid import filter_heatmap_points

__all__ = ["build_commune_risk_summary", "filter_heatmap_points"]


def _risk_level_from_pct(pct_eleve: float, pct_modere: float, avg_risk: float) -> str:
    if pct_eleve >= 25 or avg_risk >= 0.65:
        return "eleve"
    if pct_modere >= 30 or pct_eleve >= 10 or avg_risk >= 0.4:
        return "modere"
    return "faible"


def build_commune_risk_summary() -> list[dict[str, Any]]:
    """Agrège le risque observé par commune (signalements validés — requête Django)."""
    from locations.models import Commune
    from reports.models import Report

    summaries: list[dict[str, Any]] = []
    for commune in Commune.objects.all().order_by("nom"):
        qs = Report.objects.filter(status="V").filter(
            Q(quartier__commune=commune) | Q(location__icontains=commune.nom)
        )
        count = qs.count()
        if count == 0:
            continue

        degrees = list(qs.values_list("degree", flat=True))
        pct_f = round(sum(1 for d in degrees if d == "F") / count * 100, 1)
        pct_m = round(sum(1 for d in degrees if d == "M") / count * 100, 1)
        pct_e = round(sum(1 for d in degrees if d == "E") / count * 100, 1)
        avg_risk = round((pct_f * 0.0 + pct_m * 0.5 + pct_e * 1.0) / 100, 3)

        lats = [r.latitude for r in qs if r.latitude is not None]
        lons = [r.longitude for r in qs if r.longitude is not None]
        centroid = None
        if lats and lons:
            centroid = {
                "latitude": round(float(np.mean(lats)), 5),
                "longitude": round(float(np.mean(lons)), 5),
            }

        summaries.append(
            {
                "commune_id": commune.id,
                "commune_nom": commune.nom,
                "report_count": count,
                "pct_faible": pct_f,
                "pct_modere": pct_m,
                "pct_eleve": pct_e,
                "avg_risk_score": avg_risk,
                "risk_level": _risk_level_from_pct(pct_e, pct_m, avg_risk),
                "centroid": centroid,
            }
        )
    return summaries
