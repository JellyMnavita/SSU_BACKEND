from django.urls import path

from .views import (
    AdminSafetyDashboardView,
    CheckInConfirmView,
    CheckInMissedView,
    CheckInStartView,
    EmergencyAlertView,
    MobileBatchSyncView,
    SafetyAlertListView,
    SafetyAlertMarkReadView,
    SafetyAlertDeleteView,
    SafetyAlertClearView,
    SafetyAlertUnreadCountView,
    TrackingPointCreateView,
    TrackingSessionLiveView,
    TrackingSessionStopView,
    TripStartView,
    TripStopView,
    TrustedContactDetailView,
    TrustedContactListCreateView,
)

urlpatterns = [
    # Contacts de confiance
    path(
        "safety/trusted-contacts/",
        TrustedContactListCreateView.as_view(),
        name="trusted-contacts-list",
    ),
    path(
        "safety/trusted-contacts/<int:pk>/",
        TrustedContactDetailView.as_view(),
        name="trusted-contacts-detail",
    ),
    # SOS / signalement rapide + suivi
    path(
        "safety/emergency/",
        EmergencyAlertView.as_view(),
        name="safety-emergency",
    ),
    path(
        "safety/tracking/<str:token>/",
        TrackingSessionLiveView.as_view(),
        name="tracking-live",
    ),
    path(
        "safety/tracking/<str:token>/stop/",
        TrackingSessionStopView.as_view(),
        name="tracking-stop",
    ),
    path(
        "safety/tracking/<str:token>/points/",
        TrackingPointCreateView.as_view(),
        name="tracking-point",
    ),
    # Trajets
    path("safety/trips/start/", TripStartView.as_view(), name="trip-start"),
    path("safety/trips/<int:pk>/stop/", TripStopView.as_view(), name="trip-stop"),
    # Check-in
    path("safety/check-ins/start/", CheckInStartView.as_view(), name="checkin-start"),
    path(
        "safety/check-ins/<int:pk>/confirm/",
        CheckInConfirmView.as_view(),
        name="checkin-confirm",
    ),
    path(
        "safety/check-ins/<int:pk>/missed/",
        CheckInMissedView.as_view(),
        name="checkin-missed",
    ),
    # Sync batch mobile
    path("safety/sync/batch/", MobileBatchSyncView.as_view(), name="safety-sync-batch"),
    # Alertes reçues (contacts de confiance avec compte Bokengi)
    path("safety/alerts/received/", SafetyAlertListView.as_view(), name="safety-alerts-received"),
    path(
        "safety/alerts/unread-count/",
        SafetyAlertUnreadCountView.as_view(),
        name="safety-alerts-unread-count",
    ),
    path(
        "safety/alerts/<int:pk>/read/",
        SafetyAlertMarkReadView.as_view(),
        name="safety-alert-read",
    ),
    path(
        "safety/alerts/<int:pk>/",
        SafetyAlertDeleteView.as_view(),
        name="safety-alert-delete",
    ),
    path(
        "safety/alerts/clear/",
        SafetyAlertClearView.as_view(),
        name="safety-alerts-clear",
    ),
    # Admin / gov
    path(
        "admin/safety/dashboard/",
        AdminSafetyDashboardView.as_view(),
        name="admin-safety-dashboard",
    ),
]
