"""Construction et envoi du rapport hebdomadaire sécurité."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

from reports.models import Report

from .services import _activity_last_7_days, _commune_stats, _risk_label, build_company_dashboard

logger = logging.getLogger(__name__)


def _user_role_code(user) -> str:
    if not getattr(user, "type_user", None):
        return "USER"
    return getattr(user.type_user, "code_typeUser", None) or "USER"


def build_city_weekly_summary(*, days: int = 7) -> dict:
    validated_qs = Report.objects.filter(status="V").select_related(
        "quartier", "quartier__commune"
    )
    since = timezone.now() - timedelta(days=days)
    recent = validated_qs.filter(created_at__gte=since)
    high_count = recent.filter(degree="E").count()
    total = recent.count()
    return {
        "period_days": days,
        "global_risk_label": _risk_label(high_count, total),
        "validated_incidents": total,
        "high_risk_incidents": high_count,
        "degree_breakdown": {
            "eleve": recent.filter(degree="E").count(),
            "moyen": recent.filter(degree="M").count(),
            "faible": recent.filter(degree="F").count(),
        },
        "activity_last_7_days": _activity_last_7_days(validated_qs),
        "top_communes": _commune_stats(validated_qs, days=days)[:8],
    }


def build_weekly_report_context(user) -> dict:
    role = _user_role_code(user)
    now = timezone.localtime()
    period_end = now.date()
    period_start = period_end - timedelta(days=6)
    frontend_url = (getattr(settings, "FRONTEND_URL", None) or "http://localhost").rstrip("/")

    base = {
        "username": user.username,
        "email": user.email,
        "app_name": getattr(settings, "APP_NAME", "SSU Bokengi"),
        "support_email": getattr(settings, "SUPPORT_EMAIL", None),
        "period_label": f"{period_start.strftime('%d/%m/%Y')} — {period_end.strftime('%d/%m/%Y')}",
        "dashboard_url": f"{frontend_url}/dashboard",
        "sites_url": f"{frontend_url}/dashboard/company-sites",
        "profile_url": f"{frontend_url}/dashboard/profile",
        "generated_at": now.strftime("%d/%m/%Y %H:%M"),
    }

    if role == "COMPANY":
        dashboard = build_company_dashboard(user)
        return {
            **base,
            "report_type": "organization",
            "organization_name": dashboard["organization_name"],
            "dashboard": dashboard,
        }

    summary = build_city_weekly_summary(days=7)
    return {
        **base,
        "report_type": "city",
        "summary": summary,
    }


def send_weekly_report_email(user, *, dry_run: bool = False) -> bool:
    if not user.email:
        logger.warning("Rapport hebdo ignoré pour %s : pas d'email", user.pk)
        return False

    prefs = user.merged_notification_preferences()
    if not prefs.get("weekly_report", True):
        return False

    context = build_weekly_report_context(user)
    subject = (
        f"[{context['app_name']}] Rapport sécurité — {context['organization_name']}"
        if context["report_type"] == "organization"
        else f"[{context['app_name']}] Résumé sécurité Kinshasa — semaine"
    )

    html_content = render_to_string("emails/weekly_security_report.html", context)
    plain_lines = [
        f"Bonjour {user.username},",
        "",
        f"Période : {context['period_label']}",
    ]
    if context["report_type"] == "organization":
        d = context["dashboard"]
        plain_lines.extend(
            [
                f"Organisation : {d['organization_name']}",
                f"Risque Kinshasa : {d['global_risk_label']}",
                f"Incidents validés (30j) : {d['validated_incidents_30d']}",
                f"Alertes près de vos sites : {d['alerts_near_sites']}",
                f"Sites actifs : {d['active_sites_count']} / {d['sites_count']}",
                "",
                "Brief :",
                *[f"- {line}" for line in d.get("security_brief", [])[:5]],
            ]
        )
    else:
        s = context["summary"]
        plain_lines.extend(
            [
                f"Risque Kinshasa ({s['period_days']}j) : {s['global_risk_label']}",
                f"Incidents validés : {s['validated_incidents']}",
                f"Risque élevé : {s['high_risk_incidents']}",
            ]
        )
    plain_lines.extend(["", f"Tableau de bord : {context['dashboard_url']}"])

    if dry_run:
        logger.info("DRY-RUN rapport hebdo → %s (%s)", user.email, context["report_type"])
        return True

    from users.email_utils import send_transactional_email

    send_transactional_email(
        subject=subject,
        plain_body="\n".join(plain_lines),
        html_body=html_content,
        to=[user.email],
    )
    logger.info("Rapport hebdo envoyé à %s (%s)", user.email, context["report_type"])
    return True


def users_for_weekly_reports():
    from users.models import User

    return (
        User.objects.filter(is_active=True, is_verified=True)
        .exclude(email="")
        .select_related("type_user")
    )
