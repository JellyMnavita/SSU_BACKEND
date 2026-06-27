"""Agrégations sécurité pour l'espace entreprise Kinshasa."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta

from django.utils import timezone

from reports.models import Report

from .models import CompanySite

INCIDENT_LABELS = {
    "vol": "Vol / cambriolage",
    "kidnapping": "Enlèvement / tentative",
    "agression": "Agression",
    "violence": "Violence armée",
    "vandalisme": "Vandalisme",
    "accident": "Accident",
    "autre": "Autre",
}

DEGREE_WEIGHT = {"E": 3, "M": 2, "F": 1}


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _report_commune(report: Report) -> str | None:
    if report.quartier_id and report.quartier and report.quartier.commune_id:
        return report.quartier.commune.nom
    location = (report.location or "").lower()
    from locations.models import Commune

    for commune in Commune.objects.only("nom"):
        if commune.nom.lower() in location:
            return commune.nom
    return None


def _risk_label(high: int, total: int) -> str:
    if high > 0:
        return "Vigilance"
    if total > 5:
        return "Modéré"
    if total > 0:
        return "Calme"
    return "Stable"


def _activity_last_7_days(qs) -> list[dict]:
    today = timezone.localdate()
    start = today - timedelta(days=6)
    start_dt = timezone.make_aware(datetime.combine(start, time.min))
    day_labels = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
    counts: dict = defaultdict(int)
    for created_at in qs.filter(created_at__gte=start_dt).values_list("created_at", flat=True):
        local_day = timezone.localtime(created_at).date()
        if start <= local_day <= today:
            counts[local_day] += 1
    return [
        {
            "date": (start + timedelta(days=i)).isoformat(),
            "label": day_labels[(start + timedelta(days=i)).weekday()],
            "count": counts.get(start + timedelta(days=i), 0),
        }
        for i in range(7)
    ]


def _commune_stats(validated_qs, *, days: int = 30) -> list[dict]:
    since = timezone.now() - timedelta(days=days)
    recent = validated_qs.filter(created_at__gte=since).select_related(
        "quartier", "quartier__commune"
    )
    prev_start = since - timedelta(days=days)
    previous = validated_qs.filter(created_at__gte=prev_start, created_at__lt=since)

    by_commune: dict[str, dict] = defaultdict(
        lambda: {"total": 0, "high": 0, "medium": 0, "types": Counter()}
    )
    prev_counts: dict[str, int] = defaultdict(int)

    for report in recent:
        commune = _report_commune(report)
        if not commune:
            continue
        bucket = by_commune[commune]
        bucket["total"] += 1
        if report.degree == "E":
            bucket["high"] += 1
        elif report.degree == "M":
            bucket["medium"] += 1
        inc = report.incident_type or report.ai_incident_type or "autre"
        bucket["types"][inc] += 1

    for report in previous:
        commune = _report_commune(report)
        if commune:
            prev_counts[commune] += 1

    rows = []
    for commune, data in by_commune.items():
        prev = prev_counts.get(commune, 0)
        cur = data["total"]
        if cur > prev:
            trend = "up"
        elif cur < prev:
            trend = "down"
        else:
            trend = "stable"
        dominant = data["types"].most_common(1)
        rows.append(
            {
                "commune": commune,
                "total": data["total"],
                "high": data["high"],
                "medium": data["medium"],
                "trend": trend,
                "dominant_incident": dominant[0][0] if dominant else "autre",
                "dominant_incident_label": INCIDENT_LABELS.get(
                    dominant[0][0] if dominant else "autre", "Autre"
                ),
                "risk_label": _risk_label(data["high"], data["total"]),
            }
        )
    rows.sort(key=lambda r: (r["high"], r["total"]), reverse=True)
    return rows


def _alerts_near_sites(sites: list[CompanySite], validated_qs, *, limit: int = 20) -> list[dict]:
    if not sites:
        return []

    since = timezone.now() - timedelta(days=14)
    candidates = list(
        validated_qs.filter(created_at__gte=since, latitude__isnull=False, longitude__isnull=False)
    )
    alerts: list[dict] = []

    for report in candidates:
        best_site = None
        best_dist = None
        for site in sites:
            dist = _haversine_m(site.latitude, site.longitude, report.latitude, report.longitude)
            if dist <= site.alert_radius_m and (best_dist is None or dist < best_dist):
                best_dist = dist
                best_site = site
        if best_site is None:
            continue
        alerts.append(
            {
                "id": report.id,
                "description": (report.description or "")[:200],
                "location": report.location,
                "degree": report.degree,
                "incident_type": report.incident_type or report.ai_incident_type or "autre",
                "created_at": report.created_at.isoformat(),
                "distance_m": round(best_dist or 0),
                "site_id": best_site.id,
                "site_name": best_site.name,
            }
        )

    alerts.sort(key=lambda a: a["created_at"], reverse=True)
    return alerts[:limit]


def _build_brief(
    *,
    global_label: str,
    top_communes: list[dict],
    sites: list[CompanySite],
    near_alerts: list[dict],
) -> list[str]:
    lines: list[str] = []
    lines.append(f"Contexte Kinshasa : niveau {global_label.lower()} sur les 30 derniers jours.")

    if sites:
        active = [s for s in sites if not s.is_planned]
        planned = [s for s in sites if s.is_planned]
        if active:
            lines.append(
                f"{len(active)} site(s) opérationnel(s) surveillé(s) — "
                f"{len(near_alerts)} alerte(s) validée(s) à proximité (14 j)."
            )
        if planned:
            lines.append(
                f"{len(planned)} implantation(s) envisagée(s) : comparez les communes avant décision."
            )

    if top_communes:
        top = top_communes[0]
        lines.append(
            f"Commune la plus signalée : {top['commune']} "
            f"({top['total']} incidents, risque {top['risk_label'].lower()})."
        )

    high_communes = [c["commune"] for c in top_communes if c["high"] > 0][:3]
    if high_communes:
        lines.append(
            "Zones à vigilance renforcée : " + ", ".join(high_communes) + "."
        )

    if not near_alerts and sites:
        lines.append("Aucune alerte validée récente dans le rayon de vos sites.")
    elif near_alerts:
        lines.append(
            f"Dernière alerte proche : {near_alerts[0]['location']} "
            f"({near_alerts[0]['distance_m']} m du site {near_alerts[0]['site_name']})."
        )

    lines.append(
        "Recommandation : planifiez les déplacements en journée, privilégiez les itinéraires sûrs "
        "et briefez vos équipes terrain chaque matin."
    )
    return lines


def build_company_dashboard(user) -> dict:
    sites = list(CompanySite.objects.filter(user=user))
    validated_qs = Report.objects.filter(status="V").select_related(
        "quartier", "quartier__commune"
    )
    org_reports = Report.objects.filter(user=user)

    since_30 = timezone.now() - timedelta(days=30)
    kinshasa_recent = validated_qs.filter(created_at__gte=since_30)
    high_count = kinshasa_recent.filter(degree="E").count()
    total_validated = kinshasa_recent.count()
    global_label = _risk_label(high_count, total_validated)

    top_communes = _commune_stats(validated_qs, days=30)
    near_alerts = _alerts_near_sites(sites, validated_qs)

    site_communes = {s.commune for s in sites}
    site_commune_stats = [c for c in top_communes if c["commune"] in site_communes]

    degree_breakdown = {
        "eleve": kinshasa_recent.filter(degree="E").count(),
        "moyen": kinshasa_recent.filter(degree="M").count(),
        "faible": kinshasa_recent.filter(degree="F").count(),
    }

    return {
        "organization_name": user.username,
        "global_risk_label": global_label,
        "validated_incidents_30d": total_validated,
        "high_risk_incidents_30d": high_count,
        "sites_count": len(sites),
        "active_sites_count": sum(1 for s in sites if not s.is_planned),
        "planned_sites_count": sum(1 for s in sites if s.is_planned),
        "alerts_near_sites": len(near_alerts),
        "my_reports_count": org_reports.count(),
        "degree_breakdown": degree_breakdown,
        "activity_last_7_days": _activity_last_7_days(validated_qs),
        "top_communes": top_communes[:10],
        "site_commune_stats": site_commune_stats,
        "recent_alerts_near_sites": near_alerts[:8],
        "security_brief": _build_brief(
            global_label=global_label,
            top_communes=top_communes,
            sites=sites,
            near_alerts=near_alerts,
        ),
    }
