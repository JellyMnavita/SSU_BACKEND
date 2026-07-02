import csv
import hashlib
import json
from datetime import datetime, time, timedelta

from django.core.cache import cache
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from users.permissions import IsAdminUserType, IsGovUser, IsAdminOrGov
from users.models import User
from citizens.models import Citizen
from .models import Report, ReportAISettings, ScrapedReport
from .ingest_serializers import ScrapedReportSerializer
from .ai_settings_serializers import ReportAISettingsSerializer
from django.conf import settings

from reports.tasks import process_report_ai

from .notifications import notify_report_status_change, update_report_status
from .public_visibility import apply_public_map_retention, get_public_map_retention_days
from .moderation_feedback import record_human_moderation_feedback
from .cache_utils import invalidate_reports_list_cache
from .serializers import (
    AdminReportEditSerializer,
    ReportDetailsSerializer,
    ReportNotificationSerializer,
    ReportSerializer,
    ReportStatusSerializer,
    UserReportUpdateSerializer,
)
from .report_quality import SYNTHETIC_URL_PREFIX
from company.services import _build_brief, _commune_stats, _risk_label


class ReportCreateView(generics.CreateAPIView):
    serializer_class = ReportSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        user = request.user if request.user.is_authenticated else None

        if user:
            if user.type_user.code_typeUser not in ["ADMIN", "USER"]:
                return Response(
                    {"error": "Seuls les ADMIN et USER peuvent créer des reports"},
                    status=status.HTTP_403_FORBIDDEN,
                )
        elif "citizen_data" not in request.data:
            return Response(
                {"error": "Les citoyens doivent fournir leurs informations"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Évite request.data.copy() : deepcopy échoue sur les fichiers multipart.
        data = {key: request.data.get(key) for key in request.data}
        for key in request.FILES:
            data[key] = request.FILES.get(key)

        if user:
            data["source"] = "U"
            data["user"] = user.id
        else:
            data["source"] = "C"

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        report = serializer.save()

        if getattr(settings, "AI_GATEWAY_ENABLED", True):
            report.ai_processing_status = "pending"
            report.save(update_fields=["ai_processing_status"])
            process_report_ai.delay(report.id)
        else:
            report.ai_processing_status = "skipped"
            report.save(update_fields=["ai_processing_status"])

        response_data = ReportSerializer(report).data
        response_data["ai_processing"] = {
            "status": report.ai_processing_status,
            "message": (
                "Analyse IA en cours en arrière-plan."
                if report.ai_processing_status == "pending"
                else "Analyse IA désactivée."
            ),
        }

        return Response(response_data, status=status.HTTP_201_CREATED)


def _apply_report_filters(qs, request):
    """Filtres partagés entre la liste paginée et l'export CSV admin."""
    status_param = request.query_params.get("status")
    if status_param:
        statuses = [s.strip() for s in status_param.split(",") if s.strip() in ("P", "V", "R")]
        if len(statuses) == 1:
            qs = qs.filter(status=statuses[0])
        elif len(statuses) > 1:
            qs = qs.filter(status__in=statuses)

    degree_param = request.query_params.get("degree")
    if degree_param:
        degrees = [d.strip() for d in degree_param.split(",") if d.strip() in ("F", "M", "E")]
        if len(degrees) == 1:
            qs = qs.filter(degree=degrees[0])
        elif len(degrees) > 1:
            qs = qs.filter(degree__in=degrees)

    quartier_param = request.query_params.get("quartier")
    if quartier_param:
        try:
            qs = qs.filter(quartier_id=int(quartier_param))
        except (TypeError, ValueError):
            pass

    search = (request.query_params.get("search") or "").strip()
    if search:
        search_q = (
            Q(description__icontains=search)
            | Q(location__icontains=search)
            | Q(user__username__icontains=search)
            | Q(citizen__name__icontains=search)
            | Q(citizen__lastname__icontains=search)
        )
        id_search = search[4:].strip() if search.upper().startswith("RPT-") else search
        if id_search.isdigit():
            search_q |= Q(id=int(id_search))
        qs = qs.filter(search_q)

    source_param = (request.query_params.get("source") or "").strip().upper()
    if source_param:
        allowed_sources = ("U", "C", "S", "A", "O", "Q", "W")
        sources = [s.strip() for s in source_param.split(",") if s.strip() in allowed_sources]
        if len(sources) == 1:
            qs = qs.filter(source=sources[0])
        elif len(sources) > 1:
            qs = qs.filter(source__in=sources)

    ai_status = (request.query_params.get("ai_processing_status") or "").strip().lower()
    if ai_status in ("pending", "processing", "completed", "failed", "skipped"):
        qs = qs.filter(ai_processing_status=ai_status)

    reporter_type = (request.query_params.get("reporter_type") or "").strip().lower()
    if reporter_type == "user":
        qs = qs.filter(source="U")
    elif reporter_type == "citizen":
        qs = qs.filter(source="C")
    elif reporter_type == "system":
        qs = qs.filter(source="S")
    elif reporter_type == "synthetic":
        qs = qs.filter(external_source_url__startswith=SYNTHETIC_URL_PREFIX)

    user_type = (request.query_params.get("user_type") or "").strip().upper()
    if user_type in ("ADMIN", "USER", "GOV", "COMPANY"):
        qs = qs.filter(user__type_user__code_typeUser=user_type)

    return qs


class ReportListView(generics.ListAPIView):
    serializer_class = ReportSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = []

    class ReportPagination(PageNumberPagination):
        page_size = 20
        page_size_query_param = "page_size"
        max_page_size = 500

    pagination_class = ReportPagination

    def get_queryset(self):
        user = self.request.user
        base = Report.objects.select_related("user", "citizen", "quartier", "quartier__commune")

        if user.is_authenticated and user.type_user.code_typeUser in ("ADMIN", "GOV"):
            qs = base.all()
        else:
            qs = (
                base.filter(status="V")
                .exclude(external_source_url__startswith=SYNTHETIC_URL_PREFIX)
                .exclude(source="O")
            )
            qs = apply_public_map_retention(qs)

        return _apply_report_filters(qs, self.request).order_by("-created_at")

    def list(self, request, *args, **kwargs):
        user = request.user
        visibility_scope = (
            "admin_all"
            if user.is_authenticated
            and getattr(user.type_user, "code_typeUser", None) in ("ADMIN", "GOV")
            else "public_validated"
        )
        cache_key_payload = {
            "scope": visibility_scope,
            "retention_days": (
                get_public_map_retention_days() if visibility_scope == "public_validated" else None
            ),
            "params": {
                "status": request.query_params.get("status"),
                "degree": request.query_params.get("degree"),
                "quartier": request.query_params.get("quartier"),
                "search": request.query_params.get("search"),
                "source": request.query_params.get("source"),
                "ai_processing_status": request.query_params.get("ai_processing_status"),
                "reporter_type": request.query_params.get("reporter_type"),
                "user_type": request.query_params.get("user_type"),
                "page": request.query_params.get("page", "1"),
                "page_size": request.query_params.get("page_size", "20"),
            },
        }
        cache_key = "reports:list:" + hashlib.md5(
            json.dumps(cache_key_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()

        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)

        response = super().list(request, *args, **kwargs)
        # short TTL to keep dashboard fresh while still reducing DB load
        cache.set(cache_key, response.data, timeout=60)
        return response


class ReportDetailView(generics.RetrieveAPIView):
    queryset = Report.objects.all()
    serializer_class = ReportDetailsSerializer
    permission_classes = [permissions.AllowAny]  # Lecture ouverte à tous


# Les vues suivantes restent réservées aux admins
class ReportUpdateView(generics.UpdateAPIView):
    queryset = Report.objects.all()
    serializer_class = AdminReportEditSerializer
    permission_classes = [IsAdminUserType]

    def perform_update(self, serializer):
        old_status = self.get_object().status
        report = serializer.save()
        if old_status != report.status:
            record_human_moderation_feedback(report, report.status, self.request.user)
            notify_report_status_change(report, old_status)
        invalidate_reports_list_cache()


class ReportDeleteView(generics.DestroyAPIView):
    queryset = Report.objects.all()
    permission_classes = [IsAdminUserType]

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        invalidate_reports_list_cache()


class ValidateReportView(generics.UpdateAPIView):
    queryset = Report.objects.all()
    serializer_class = ReportStatusSerializer
    permission_classes = [IsAdminUserType]

    def patch(self, request, *args, **kwargs):
        report = self.get_object()
        previous = report.status
        report.status = "V"
        report.save()
        record_human_moderation_feedback(report, "V", request.user)
        invalidate_reports_list_cache()
        notify_report_status_change(report, previous)
        serializer = self.get_serializer(report)
        return Response({
            "status": "report validated",
            "report": serializer.data
        })


class RejectReportView(generics.UpdateAPIView):
    queryset = Report.objects.all()
    permission_classes = [IsAdminUserType]

    def patch(self, request, *args, **kwargs):
        report = self.get_object()
        previous = report.status
        report.status = "R"
        report.save()
        record_human_moderation_feedback(report, "R", request.user)
        invalidate_reports_list_cache()
        notify_report_status_change(report, previous)
        return Response({"status": "report rejected"})

# Vues spécialisées
class UserReportsListView(generics.ListAPIView):
    serializer_class = ReportSerializer
    
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.type_user.code_typeUser in ["ADMIN", "USER"]:
            return (
                Report.objects.filter(
                    Q(user=user) | Q(citizen__email__iexact=user.email)
                )
                .distinct()
                .order_by("-created_at")
            )
        return Report.objects.none()


class UserReportUpdateView(generics.UpdateAPIView):
    serializer_class = UserReportUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["patch", "put"]

    def get_queryset(self):
        user = self.request.user
        if user.type_user.code_typeUser not in ["ADMIN", "USER"]:
            return Report.objects.none()
        return Report.objects.filter(
            Q(user=user) | Q(citizen__email__iexact=user.email)
        ).distinct().exclude(status="V")

    def perform_update(self, serializer):
        serializer.save()
        invalidate_reports_list_cache()


class CitizenReportsListView(generics.ListAPIView):
    serializer_class = ReportSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        citizen_email = self.request.query_params.get("email")
        if not citizen_email:
            return Report.objects.none()

        return Report.objects.filter(citizen__email=citizen_email).order_by(
            "-created_at"
        )


def _activity_last_7_days():
    """Compte les signalements par jour sur les 7 derniers jours (inclus aujourd'hui)."""
    today = timezone.localdate()
    start = today - timedelta(days=6)
    day_labels = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
    start_dt = timezone.make_aware(datetime.combine(start, time.min))

    counts_by_day = {}
    for report in Report.objects.filter(created_at__gte=start_dt).only("created_at"):
        local_day = timezone.localtime(report.created_at).date()
        if start <= local_day <= today:
            counts_by_day[local_day] = counts_by_day.get(local_day, 0) + 1

    activity = []
    for offset in range(7):
        day = start + timedelta(days=offset)
        activity.append(
            {
                "date": day.isoformat(),
                "label": day_labels[day.weekday()],
                "count": counts_by_day.get(day, 0),
            }
        )
    return activity


class ReportAISettingsView(APIView):
    """Paramètres IA signalements (admin) — ex. modération automatique."""

    permission_classes = [IsAdminUserType]

    def get(self, request):
        from django.core.cache import cache

        from ai_gateway.clients.base import AIServiceError
        from ai_gateway.clients.nlp import NLPServiceClient

        settings_obj = ReportAISettings.get_solo()
        payload = ReportAISettingsSerializer(settings_obj).data

        from reports.vision_dataset import dataset_stats

        nlp_model = {"available": False, "error": "service indisponible"}
        try:
            nlp_model = {"available": True, **NLPServiceClient().health()}
        except AIServiceError as exc:
            nlp_model["error"] = str(exc)

        last_train = cache.get("ai:train:last_run")
        payload["nlp_model"] = nlp_model
        payload["last_model_training"] = last_train
        payload["vision_dataset"] = dataset_stats()

        from ai_gateway import conf as ai_conf

        beat = getattr(settings, "CELERY_BEAT_SCHEDULE", {}) or {}
        schedule_labels = {
            "refresh_scrapping_cache_every30min": "Rafraîchissement cache scraping — toutes les 30 min",
            "ingest_security_news_hourly": "Ingestion actualités sécurité — chaque heure (:15)",
            "export_reports_csv_hourly": "Export CSV signalements — chaque heure (:05)",
            "train_prediction_model_hourly": "Entraînement prédiction spatiale — chaque heure (:10)",
            "train_vision_model_weekly": "Entraînement vision — dimanches 3h (si activé + nouvelles images)",
            "send_weekly_security_reports": "Rapports hebdomadaires entreprises — lundis 7h",
        }
        payload["system"] = {
            "news_ingest_enabled": getattr(settings, "NEWS_INGEST_ENABLED", True),
            "ai_gateway_enabled": ai_conf.AI_GATEWAY_ENABLED,
            "ai_use_microservices": ai_conf.AI_USE_MICROSERVICES,
            "frontend_url": getattr(settings, "FRONTEND_URL", ""),
            "celery_schedules": [
                {"id": key, "label": schedule_labels.get(key, key)}
                for key in beat.keys()
            ],
        }
        return Response(payload)

    def patch(self, request):
        settings_obj = ReportAISettings.get_solo()
        serializer = ReportAISettingsSerializer(
            settings_obj, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class NewsIngestStatusView(APIView):
    """Tableau de bord ingestion — stats, dernière exécution, journal des articles."""

    permission_classes = [IsAdminUserType]

    def get(self, request):
        from scrapping.services.fetcher import list_news_sources

        status_filter = request.query_params.get("status")
        qs = ScrapedReport.objects.select_related("report").all()
        if status_filter in ("P", "T", "R"):
            qs = qs.filter(status=status_filter)

        page_size = min(int(request.query_params.get("page_size", 30)), 100)
        page = max(int(request.query_params.get("page", 1)), 1)
        total = qs.count()
        offset = (page - 1) * page_size
        items = qs[offset : offset + page_size]

        settings_obj = ReportAISettings.get_solo()
        system_reports = Report.objects.filter(source="S")
        scraped_counts = {
            "total": ScrapedReport.objects.count(),
            "processed": ScrapedReport.objects.filter(status="T").count(),
            "rejected": ScrapedReport.objects.filter(status="R").count(),
            "pending": ScrapedReport.objects.filter(status="P").count(),
        }

        return Response(
            {
                "auto_ingest_news": settings_obj.auto_ingest_news,
                "news_ingest_enabled": getattr(settings, "NEWS_INGEST_ENABLED", True),
                "sources": [
                    {"id": s["id"], "name": s["name"], "list_url": s["list_url"]}
                    for s in list_news_sources()
                ],
                "last_run": cache.get("ingest:last_run"),
                "stats": {
                    **scraped_counts,
                    "system_reports": system_reports.count(),
                    "system_reports_today": system_reports.filter(
                        created_at__date=timezone.localdate()
                    ).count(),
                },
                "articles": ScrapedReportSerializer(items, many=True).data,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": max(1, (total + page_size - 1) // page_size),
                },
            }
        )


class NewsIngestView(APIView):
    """Déclenche manuellement l'ingestion actualités → signalements source=S."""

    permission_classes = [IsAdminUserType]

    def post(self, request):
        from scrapping.tasks import ingest_security_news

        max_articles = int(request.data.get("max_articles", 50))
        async_mode = request.data.get("async", True)
        if async_mode:
            task = ingest_security_news.delay(max_articles=max_articles)
            return Response(
                {"status": "queued", "task_id": task.id, "max_articles": max_articles},
                status=status.HTTP_202_ACCEPTED,
            )

        from scrapping.services.ingest import run_news_ingest

        stats = run_news_ingest(max_articles=max_articles, force=True)
        return Response(stats)


class TrainModelsView(APIView):
    """Lance manuellement le réentraînement des modèles IA (admin)."""

    permission_classes = [IsAdminUserType]

    def get(self, request):
        last_run = cache.get("ai:train:last_run")
        running = cache.get("ai:train:running")
        return Response({"last_run": last_run, "running": running})

    def post(self, request):
        from .tasks import train_ai_models

        model = request.data.get("model", "all")
        valid = {"all", "prediction", "nlp", "vision"}
        if model not in valid:
            return Response(
                {"error": f"model doit être parmi : {', '.join(sorted(valid))}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        async_mode = request.data.get("async", True)
        if async_mode:
            task = train_ai_models.delay(model=model)
            return Response(
                {"status": "queued", "task_id": task.id, "model": model},
                status=status.HTTP_202_ACCEPTED,
            )

        result = train_ai_models(model=model)
        return Response(result)


def _filtered_reports_queryset(request):
    qs = Report.objects.select_related("user", "citizen", "quartier", "quartier__commune").all()
    return _apply_report_filters(qs, request).order_by("-created_at")


class ExportReportsView(APIView):
    """Export CSV des signalements (journal admin), avec les mêmes filtres que la liste."""

    permission_classes = [IsAdminUserType]

    def get(self, request):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        filename = f"signalements_{timezone.localdate().isoformat()}.csv"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response.write("\ufeff")

        writer = csv.writer(response)
        writer.writerow([
            "ID",
            "Date",
            "Statut",
            "Gravité",
            "Lieu",
            "Latitude",
            "Longitude",
            "Quartier",
            "Description",
            "Source",
            "Reporter",
            "Type incident IA",
            "Reco modération IA",
            "Confiance modération IA",
            "URL source externe",
        ])

        status_labels = dict(Report.STATUS_CHOICES)
        degree_labels = dict(Report.DEGREE_CHOICES)
        source_labels = dict(Report.SOURCE_CHOICES)
        moderation_labels = {"V": "Valider", "R": "Rejeter", "P": "En attente"}

        for report in _filtered_reports_queryset(request).iterator():
            if report.user:
                reporter = report.user.username
            elif report.citizen:
                reporter = f"{report.citizen.name} {report.citizen.lastname}".strip()
            else:
                reporter = "—"

            quartier_name = ""
            if report.quartier:
                commune = getattr(report.quartier.commune, "nom", "") or ""
                quartier_name = f"{report.quartier.nom}, {commune}".strip(", ")

            writer.writerow([
                report.id,
                report.created_at.strftime("%Y-%m-%d %H:%M:%S") if report.created_at else "",
                status_labels.get(report.status, report.status),
                degree_labels.get(report.degree, report.degree),
                report.location,
                report.latitude,
                report.longitude,
                quartier_name,
                (report.description or "").replace("\n", " ").strip(),
                source_labels.get(report.source, report.source),
                reporter,
                report.ai_incident_type or "",
                moderation_labels.get(
                    report.ai_moderation_recommendation,
                    report.ai_moderation_recommendation or "",
                ),
                report.ai_moderation_confidence if report.ai_moderation_confidence is not None else "",
                report.external_source_url or "",
            ])

        return response


class ReportStatsView(APIView):
    permission_classes = [IsAdminOrGov]

    def get(self, request):
        today = timezone.localdate()
        total_reports = Report.objects.count()
        open_alerts = Report.objects.filter(status="P").count()
        reports_today = Report.objects.filter(created_at__date=today).count()
        active_users = User.objects.filter(report__isnull=False).distinct().count()
        total_citizens = Citizen.objects.filter(report__isnull=False).distinct().count()
        reports_by_degree = {
            "faible": Report.objects.filter(degree="F").count(),
            "moyen": Report.objects.filter(degree="M").count(),
            "eleve": Report.objects.filter(degree="E").count(),
        }
        validated_reports = Report.objects.filter(status="V").count()
        rejected_reports = Report.objects.filter(status="R").count()

        validated_qs = Report.objects.filter(status="V").select_related(
            "quartier", "quartier__commune"
        )
        since_30 = timezone.now() - timedelta(days=30)
        kinshasa_recent = validated_qs.filter(created_at__gte=since_30)
        high_count_30d = kinshasa_recent.filter(degree="E").count()
        total_validated_30d = kinshasa_recent.count()
        global_label = _risk_label(high_count_30d, total_validated_30d)
        top_communes = _commune_stats(validated_qs, days=30)

        return Response({
            "total_reports": total_reports,
            "open_alerts": open_alerts,
            "reports_today": reports_today,
            "active_users": active_users,
            "total_citizens": total_citizens,
            "reports_by_degree": reports_by_degree,
            "validated_reports": validated_reports,
            "rejected_reports": rejected_reports,
            "activity_last_7_days": _activity_last_7_days(),
            "global_risk_label": global_label,
            "validated_incidents_30d": total_validated_30d,
            "high_risk_incidents_30d": high_count_30d,
            "degree_breakdown_30d": {
                "eleve": kinshasa_recent.filter(degree="E").count(),
                "moyen": kinshasa_recent.filter(degree="M").count(),
                "faible": kinshasa_recent.filter(degree="F").count(),
            },
            "top_communes": top_communes[:15],
            "security_brief": _build_brief(
                global_label=global_label,
                top_communes=top_communes,
                sites=[],
                near_alerts=[],
            ),
        })


class ReportNotificationListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ReportNotificationSerializer

    def get_queryset(self):
        from .models import ReportNotification

        return ReportNotification.objects.filter(recipient=self.request.user).select_related(
            "report"
        )


class ReportNotificationUnreadCountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .models import ReportNotification

        count = ReportNotification.objects.filter(
            recipient=request.user, read_at__isnull=True
        ).count()
        return Response({"unread_count": count})


class ReportNotificationMarkReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        from .models import ReportNotification

        try:
            notif = ReportNotification.objects.get(pk=pk, recipient=request.user)
        except ReportNotification.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not notif.read_at:
            notif.read_at = timezone.now()
            notif.save(update_fields=["read_at"])
        return Response(ReportNotificationSerializer(notif).data)
