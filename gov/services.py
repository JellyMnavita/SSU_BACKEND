"""Tableau de bord territorial pour les comptes gouvernement (GOV)."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from company.services import (
    _activity_last_7_days,
    _commune_stats,
    _risk_label,
)
from police.services import build_police_dashboard
from reports.models import Report


def _build_gov_brief(
    *,
    global_label: str,
    top_communes: list[dict],
    pending_count: int,
    reports_today: int,
) -> list[str]:
    lines: list[str] = []
    lines.append(
        f"Situation Kinshasa : niveau {global_label.lower()} sur les 30 derniers jours (incidents validés)."
    )
    lines.append(
        f"{pending_count} signalement(s) en attente de modération — {reports_today} reçu(s) aujourd'hui."
    )

    if top_communes:
        top = top_communes[0]
        lines.append(
            f"Commune la plus touchée : {top['commune']} "
            f"({top['total']} incidents, risque {top['risk_label'].lower()})."
        )

    rising = [c for c in top_communes if c.get("trend") == "up"][:3]
    if rising:
        lines.append(
            "Tendance à la hausse : "
            + ", ".join(f"{c['commune']} (+{c['total']})" for c in rising)
            + "."
        )

    high_communes = [c["commune"] for c in top_communes if c["high"] > 0][:4]
    if high_communes:
        lines.append(
            "Priorité intervention terrain : " + ", ".join(high_communes) + "."
        )

    lines.append(
        "Recommandation : croiser carte, prédictions et signalements citoyens "
        "pour orienter les patrouilles et la communication locale."
    )
    return lines


def build_gov_dashboard(user) -> dict:
    validated_qs = Report.objects.filter(status="V").select_related(
        "quartier", "quartier__commune"
    )
    pending_qs = Report.objects.filter(status="P").order_by("-created_at")
    today = timezone.localdate()

    since_30 = timezone.now() - timedelta(days=30)
    kinshasa_recent = validated_qs.filter(created_at__gte=since_30)
    high_count = kinshasa_recent.filter(degree="E").count()
    total_validated_30d = kinshasa_recent.count()
    global_label = _risk_label(high_count, total_validated_30d)

    top_communes = _commune_stats(validated_qs, days=30)
    priority_communes = [c for c in top_communes if c["high"] > 0][:8]

    recent_pending = list(
        pending_qs.select_related("user", "citizen")[:10].values(
            "id",
            "description",
            "location",
            "degree",
            "created_at",
            "source",
        )
    )
    for row in recent_pending:
        if row.get("created_at"):
            row["created_at"] = row["created_at"].isoformat()
        row["description"] = (row.get("description") or "")[:200]

    degree_breakdown = {
        "eleve": kinshasa_recent.filter(degree="E").count(),
        "moyen": kinshasa_recent.filter(degree="M").count(),
        "faible": kinshasa_recent.filter(degree="F").count(),
    }

    police = build_police_dashboard(user)

    return {
        "entity_name": user.username,
        "global_risk_label": global_label,
        "validated_incidents_30d": total_validated_30d,
        "high_risk_incidents_30d": high_count,
        "pending_reports": pending_qs.count(),
        "reports_today": Report.objects.filter(created_at__date=today).count(),
        "rejected_reports_30d": Report.objects.filter(
            status="R", created_at__gte=since_30
        ).count(),
        "my_reports_count": Report.objects.filter(user=user).count(),
        "degree_breakdown": degree_breakdown,
        "activity_last_7_days": _activity_last_7_days(validated_qs),
        "top_communes": top_communes[:12],
        "priority_communes": priority_communes,
        "recent_pending_reports": recent_pending[:8],
        "posts_count": police["posts_count"],
        "active_posts_count": police["active_posts_count"],
        "pending_near_posts": police["pending_near_posts"],
        "validated_near_posts": police["validated_near_posts"],
        "recent_pending_near_posts": police["recent_pending_near_posts"],
        "security_brief": _build_gov_brief(
            global_label=global_label,
            top_communes=top_communes,
            pending_count=pending_qs.count(),
            reports_today=Report.objects.filter(created_at__date=today).count(),
        ),
    }
