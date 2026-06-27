from django.contrib import admin

from .models import CheckIn, SafetyAlert, TrackingPoint, TrackingSession, Trip, TrustedContact


@admin.register(SafetyAlert)
class SafetyAlertAdmin(admin.ModelAdmin):
    list_display = ("kind", "recipient", "initiator", "read_at", "created_at")
    list_filter = ("kind", "read_at", "created_at")
    search_fields = ("recipient__username", "initiator__username", "message")
    raw_id_fields = ("recipient", "initiator", "trusted_contact", "tracking_session")


@admin.register(TrustedContact)
class TrustedContactAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email", "user", "relationship", "mobile_local_id", "created_at")
    list_filter = ("created_at",)
    search_fields = ("name", "phone", "user__username", "user__email")
    raw_id_fields = ("user",)


class TrackingPointInline(admin.TabularInline):
    model = TrackingPoint
    extra = 0
    readonly_fields = ("latitude", "longitude", "recorded_at")


@admin.register(TrackingSession)
class TrackingSessionAdmin(admin.ModelAdmin):
    list_display = (
        "token",
        "kind",
        "status",
        "user",
        "last_latitude",
        "last_longitude",
        "started_at",
        "ended_at",
    )
    list_filter = ("kind", "status", "started_at")
    search_fields = ("token", "user__username")
    raw_id_fields = ("user", "report")
    inlines = [TrackingPointInline]


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "status",
        "dest_label",
        "estimated_minutes",
        "alert_reason",
        "started_at",
    )
    list_filter = ("status", "started_at")
    search_fields = ("user__username", "dest_label", "origin_label")
    raw_id_fields = ("user", "tracking_session", "contact")


@admin.register(CheckIn)
class CheckInAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "status",
        "duration_minutes",
        "due_at",
        "confirmed_at",
        "auto_sos",
    )
    list_filter = ("status", "auto_sos", "due_at")
    search_fields = ("user__username",)
    raw_id_fields = ("user", "tracking_session")
