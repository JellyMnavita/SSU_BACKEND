from django.urls import path
from .views import (
    ReportCreateView,
    ReportDetailView,
    ReportListView,
    ReportUpdateView,
    ReportDeleteView,
    ValidateReportView,
    RejectReportView,
    UserReportsListView,
    CitizenReportsListView,
)

urlpatterns = [
    # --- Accès général ---
    path('reports/', ReportCreateView.as_view(), name='report-create'),
    path('reports/<int:pk>/', ReportDetailView.as_view(), name='report-detail'),
    path('reports/list/', ReportListView.as_view(), name='report-list'),

    # --- Vues ADMIN ---
    path('admin/reports/<int:pk>/update/', ReportUpdateView.as_view(), name='report-update'),
    path('admin/reports/<int:pk>/delete/', ReportDeleteView.as_view(), name='report-delete'),
    path('admin/reports/<int:pk>/validate/', ValidateReportView.as_view(), name='report-validate'),
    path('admin/reports/<int:pk>/reject/', RejectReportView.as_view(), name='report-reject'),

    # --- Vues spécialisées ---
    path('user/reports/', UserReportsListView.as_view(), name='user-reports'),
    path('citizen/reports/', CitizenReportsListView.as_view(), name='citizen-reports'),
]
