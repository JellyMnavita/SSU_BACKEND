from rest_framework import generics, permissions, status
from rest_framework.response import Response
from users.permissions import IsAdminUserType
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
    filterset_fields = ["status", "degree", "quartier"]
    search_fields = ["description", "location"]

    def get_queryset(self):
        user = self.request.user

        if user.is_authenticated and user.type_user.code_typeUser == "ADMIN":
            return Report.objects.all().order_by("-created_at")
        else:
            return Report.objects.filter(status="V").order_by("-created_at")


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
            return Report.objects.filter(user=user)
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
