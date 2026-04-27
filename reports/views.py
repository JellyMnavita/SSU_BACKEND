import hashlib
import json

from django.core.cache import cache
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, permissions, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from users.permissions import IsAdminUserType, IsGovUser, IsAdminOrGov
from users.models import User
from citizens.models import Citizen
from .models import Report
from .serializers import (
    ReportDetailsSerializer,
    ReportSerializer,
    ReportStatusSerializer,
)


class ReportCreateView(generics.CreateAPIView):
    serializer_class = ReportSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        user = request.user if request.user.is_authenticated else None

        if user:
            if user.type_user.code_typeUser not in ["ADMIN", "USER"]:
                return Response(
                    {"error": "Seuls les ADMIN et USER peuvent créer des reports"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            data["source"] = "U"
            data["user"] = user.id
        else:
            if "citizen_data" in data:
                data["source"] = "C"
            else:
                return Response(
                    {"error": "Les citoyens doivent fournir leurs informations"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ReportListView(generics.ListAPIView):
    serializer_class = ReportSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["status", "degree", "quartier"]
    search_fields = ["description", "location"]

    class ReportPagination(PageNumberPagination):
        page_size = 20
        page_size_query_param = "page_size"
        max_page_size = 100

    pagination_class = ReportPagination

    def get_queryset(self):
        user = self.request.user

        if user.is_authenticated and user.type_user.code_typeUser == "ADMIN":
            return Report.objects.select_related("user", "citizen", "quartier", "quartier__commune").all().order_by("-created_at")
        else:
            return Report.objects.select_related("user", "citizen", "quartier", "quartier__commune").filter(status="V").order_by("-created_at")

    def list(self, request, *args, **kwargs):
        user = request.user
        visibility_scope = (
            "admin_all"
            if user.is_authenticated and getattr(user.type_user, "code_typeUser", None) == "ADMIN"
            else "public_validated"
        )
        cache_key_payload = {
            "scope": visibility_scope,
            "params": {
                "status": request.query_params.get("status"),
                "degree": request.query_params.get("degree"),
                "quartier": request.query_params.get("quartier"),
                "search": request.query_params.get("search"),
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
    serializer_class = ReportSerializer
    permission_classes = [IsAdminUserType]


class ReportDeleteView(generics.DestroyAPIView):
    queryset = Report.objects.all()
    permission_classes = [IsAdminUserType]
    

class ValidateReportView(generics.UpdateAPIView):
    queryset = Report.objects.all()
    serializer_class = ReportStatusSerializer
    permission_classes = [IsAdminUserType]

    def patch(self, request, *args, **kwargs):
        report = self.get_object()
        report.status = "V"
        report.save()
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
        report.status = "R"
        report.save()
        return Response({"status": "report rejected"})

# Vues spécialisées
class UserReportsListView(generics.ListAPIView):
    serializer_class = ReportSerializer
    
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.type_user.code_typeUser in ["ADMIN", "USER"]:
            return Report.objects.filter(user=user).order_by("-created_at")
        return Report.objects.none() 


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


class ReportStatsView(APIView):
    permission_classes = [IsAdminOrGov]

    def get(self, request):
        total_reports = Report.objects.count()
        open_alerts = Report.objects.filter(status="P").count()
        active_users = User.objects.filter(report__isnull=False).distinct().count()
        total_citizens = Citizen.objects.filter(report__isnull=False).distinct().count()
        reports_by_degree = {
            "faible": Report.objects.filter(degree="F").count(),
            "moyen": Report.objects.filter(degree="M").count(),
            "eleve": Report.objects.filter(degree="E").count(),
        }
        validated_reports = Report.objects.filter(status="V").count()
        rejected_reports = Report.objects.filter(status="R").count()

        return Response({
            "total_reports": total_reports,
            "open_alerts": open_alerts,
            "active_users": active_users,
            "total_citizens": total_citizens,
            "reports_by_degree": reports_by_degree,
            "validated_reports": validated_reports,
            "rejected_reports": rejected_reports,
        })
