"""Statistiques postes police (utilisées par le tableau de bord gouvernement)."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from company.services import (
    _activity_last_7_days,
    _alerts_near_sites,
    _commune_stats,
    _haversine_m,
    _risk_label,
)
from reports.models import Report

from .models import PolicePost


def _posts_as_sites(posts: list[PolicePost]):
    """Adaptateur pour réutiliser la logique de proximité entreprise."""

    class _SiteProxy:
        def __init__(self, post: PolicePost):
            self.id = post.id
            self.name = post.name
            self.latitude = post.latitude
            self.longitude = post.longitude
            self.alert_radius_m = post.patrol_radius_m
            self.commune = post.commune
            self.is_planned = not post.is_active

    return [_SiteProxy(p) for p in posts]


def _pending_near_posts(posts: list[PolicePost], *, limit: int = 15) -> list[dict]:
    if not posts:
        return []
    pending = Report.objects.filter(status="P", latitude__isnull=False, longitude__isnull=False).order_by(
        "-created_at"
    )[:200]
    rows: list[dict] = []
    for report in pending:
        best_post = None
        best_dist = None
        for post in posts:
            if not post.is_active:
                continue
            dist = _haversine_m(post.latitude, post.longitude, report.latitude, report.longitude)
            if dist <= post.patrol_radius_m and (best_dist is None or dist < best_dist):
                best_dist = dist
                best_post = post
        if best_post is None:
            continue
        rows.append(
            {
                "id": report.id,
                "description": (report.description or "")[:200],
                "location": report.location,
                "degree": report.degree,
                "created_at": report.created_at.isoformat(),
                "distance_m": round(best_dist or 0),
                "post_id": best_post.id,
                "post_name": best_post.name,
            }
        )
    return rows[:limit]


def _build_police_brief(
    *,
    global_label: str,
    posts: list[PolicePost],
    pending_near: list[dict],
    validated_near_count: int,
    top_communes: list[dict],
) -> list[str]:
    lines: list[str] = []
    active = sum(1 for p in posts if p.is_active)
    lines.append(
        f"Kinshasa — niveau {global_label.lower()} (30 j). {active} poste(s) actif(s) sur la carte."
    )
    lines.append(
        f"{len(pending_near)} signalement(s) en attente dans vos zones de patrouille — "
        f"{validated_near_count} incident(s) validé(s) à proximité (14 j)."
    )
    if top_communes:
        top = top_communes[0]
        lines.append(
            f"Commune la plus touchée : {top['commune']} ({top['total']} incidents validés)."
        )
    if pending_near:
        p = pending_near[0]
        lines.append(
            f"Priorité : {p['location'] or 'Lieu non précisé'} — {p['distance_m']} m du poste {p['post_name']}."
        )
    lines.append(
        "Orientez les patrouilles selon la carte, les signalements en attente et les incidents validés proches."
    )
    return lines


def build_police_dashboard(user) -> dict:
    posts = list(PolicePost.objects.filter(user=user))
    validated_qs = Report.objects.filter(status="V").select_related(
        "quartier", "quartier__commune"
    )
    pending_qs = Report.objects.filter(status="P")

    since_30 = timezone.now() - timedelta(days=30)
    kinshasa_recent = validated_qs.filter(created_at__gte=since_30)
    high_count = kinshasa_recent.filter(degree="E").count()
    total_validated_30d = kinshasa_recent.count()
    global_label = _risk_label(high_count, total_validated_30d)

    site_proxies = _posts_as_sites(posts)
    near_validated = _alerts_near_sites(site_proxies, validated_qs)
    pending_near = _pending_near_posts(posts)
    top_communes = _commune_stats(validated_qs, days=30)

    post_communes = {p.commune for p in posts}
    post_commune_stats = [c for c in top_communes if c["commune"] in post_communes]

    return {
        "unit_name": user.username,
        "global_risk_label": global_label,
        "validated_incidents_30d": total_validated_30d,
        "high_risk_incidents_30d": high_count,
        "posts_count": len(posts),
        "active_posts_count": sum(1 for p in posts if p.is_active),
        "pending_reports": pending_qs.count(),
        "pending_near_posts": len(pending_near),
        "validated_near_posts": len(near_validated),
        "reports_today": Report.objects.filter(created_at__date=timezone.localdate()).count(),
        "degree_breakdown": {
            "eleve": kinshasa_recent.filter(degree="E").count(),
            "moyen": kinshasa_recent.filter(degree="M").count(),
            "faible": kinshasa_recent.filter(degree="F").count(),
        },
        "activity_last_7_days": _activity_last_7_days(validated_qs),
        "top_communes": top_communes[:10],
        "post_commune_stats": post_commune_stats,
        "recent_pending_near_posts": pending_near[:8],
        "recent_validated_near_posts": near_validated[:8],
        "security_brief": _build_police_brief(
            global_label=global_label,
            posts=posts,
            pending_near=pending_near,
            validated_near_count=len(near_validated),
            top_communes=top_communes,
        ),
    }
