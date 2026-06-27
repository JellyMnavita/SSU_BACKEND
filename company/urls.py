from django.urls import path

from .views import (
    CompanyCommunesRiskView,
    CompanyDashboardView,
    CompanySiteDetailView,
    CompanySiteListCreateView,
)

urlpatterns = [
    path("company/dashboard/", CompanyDashboardView.as_view(), name="company-dashboard"),
    path("company/sites/", CompanySiteListCreateView.as_view(), name="company-sites"),
    path("company/sites/<int:pk>/", CompanySiteDetailView.as_view(), name="company-site-detail"),
    path("company/communes-risk/", CompanyCommunesRiskView.as_view(), name="company-communes-risk"),
]
