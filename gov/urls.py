from django.urls import path

from .views import GovDashboardView

urlpatterns = [
    path("gov/dashboard/", GovDashboardView.as_view(), name="gov-dashboard"),
]
