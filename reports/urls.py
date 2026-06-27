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
    UserReportUpdateView,
    CitizenReportsListView,
    ReportStatsView,
    ReportAISettingsView,
    NewsIngestView,
    NewsIngestStatusView,
    TrainModelsView,
    ExportReportsView,
    ReportNotificationListView,
    ReportNotificationUnreadCountView,
    ReportNotificationMarkReadView,
)
from .vision_views import (
    ReportVisionFeedbackView,
    VisionDatasetImportView,
    VisionDatasetStatsView,
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
    path('admin/reports/stats/', ReportStatsView.as_view(), name='report-stats'),
    path('admin/reports/ai-settings/', ReportAISettingsView.as_view(), name='report-ai-settings'),
    path('admin/reports/ingest-news/', NewsIngestView.as_view(), name='report-ingest-news'),
    path('admin/reports/ingest-status/', NewsIngestStatusView.as_view(), name='report-ingest-status'),
    path('admin/reports/train-models/', TrainModelsView.as_view(), name='train-models'),
    path('admin/reports/export/', ExportReportsView.as_view(), name='report-export'),
    path('admin/vision/dataset/', VisionDatasetStatsView.as_view(), name='vision-dataset-stats'),
    path('admin/vision/dataset/import/', VisionDatasetImportView.as_view(), name='vision-dataset-import'),
    path('admin/reports/<int:pk>/vision-feedback/', ReportVisionFeedbackView.as_view(), name='report-vision-feedback'),

    # --- Vues spécialisées ---
    path('user/reports/', UserReportsListView.as_view(), name='user-reports'),
    path('user/reports/<int:pk>/', UserReportUpdateView.as_view(), name='user-report-update'),
    path('user/report-notifications/', ReportNotificationListView.as_view(), name='report-notifications'),
    path('user/report-notifications/unread-count/', ReportNotificationUnreadCountView.as_view(), name='report-notifications-unread'),
    path('user/report-notifications/<int:pk>/read/', ReportNotificationMarkReadView.as_view(), name='report-notification-read'),
    path('citizen/reports/', CitizenReportsListView.as_view(), name='citizen-reports'),
]
