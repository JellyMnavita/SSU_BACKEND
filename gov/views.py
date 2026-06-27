from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsGovUser
from .services import build_gov_dashboard


class GovDashboardView(APIView):
    permission_classes = [IsGovUser]

    def get(self, request):
        return Response(build_gov_dashboard(request.user))
