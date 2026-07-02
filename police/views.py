from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PolicePost
from .permissions import IsPoliceUser
from .serializers import PolicePostPublicSerializer, PolicePostSerializer
from .services import build_police_dashboard


class PolicePostPublicListView(generics.ListAPIView):
    """Postes actifs visibles sur la carte publique (sans authentification)."""

    serializer_class = PolicePostPublicSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None

    def get_queryset(self):
        return PolicePost.objects.filter(is_active=True).order_by("commune", "name")


class PolicePostListCreateView(generics.ListCreateAPIView):
    serializer_class = PolicePostSerializer
    permission_classes = [IsPoliceUser]

    def get_queryset(self):
        return PolicePost.objects.filter(user=self.request.user)


class PolicePostDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PolicePostSerializer
    permission_classes = [IsPoliceUser]

    def get_queryset(self):
        return PolicePost.objects.filter(user=self.request.user)


class PoliceDashboardView(APIView):
    permission_classes = [IsPoliceUser]

    def get(self, request):
        return Response(build_police_dashboard(request.user))
