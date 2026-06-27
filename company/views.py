from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CompanySite
from .permissions import IsCompanyUser
from .serializers import CompanySiteSerializer
from .services import build_company_dashboard


class CompanySiteListCreateView(generics.ListCreateAPIView):
    serializer_class = CompanySiteSerializer
    permission_classes = [IsCompanyUser]

    def get_queryset(self):
        return CompanySite.objects.filter(user=self.request.user)


class CompanySiteDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CompanySiteSerializer
    permission_classes = [IsCompanyUser]

    def get_queryset(self):
        return CompanySite.objects.filter(user=self.request.user)


class CompanyDashboardView(APIView):
    permission_classes = [IsCompanyUser]

    def get(self, request):
        return Response(build_company_dashboard(request.user))


class CompanyCommunesRiskView(APIView):
    """Comparatif communes pour implantation / expansion."""

    permission_classes = [IsCompanyUser]

    def get(self, request):
        from .services import _commune_stats
        from reports.models import Report

        days = min(int(request.query_params.get("days", 30)), 90)
        validated_qs = Report.objects.filter(status="V").select_related(
            "quartier", "quartier__commune"
        )
        return Response({"days": days, "communes": _commune_stats(validated_qs, days=days)})
