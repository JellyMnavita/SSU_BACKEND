from rest_framework import generics

from users.permissions import IsAdminUserType

from .models import Citizen
from .serializers import CitizenSerializer


class CitizenListView(generics.ListAPIView):
    queryset = (
        Citizen.objects.select_related("quartier", "quartier__commune")
        .prefetch_related(
            "alternate_data",
            "alternate_data__quartier",
            "alternate_data__quartier__commune",
        )
        .order_by("-created_at")
    )
    serializer_class = CitizenSerializer
    permission_classes = [IsAdminUserType]
