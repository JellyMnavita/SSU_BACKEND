from django.contrib import admin

from .models import Report, ReportAISettings, ScrapedReport


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "source",
        "incident_type",
        "degree",
        "status",
        "location",
        "is_witness",
        "is_anonymous",
        "user",
        "created_at",
    )
    list_filter = (
        "source",
        "incident_type",
        "degree",
        "status",
        "is_witness",
        "is_anonymous",
        "ai_processing_status",
        "created_at",
    )
    search_fields = (
        "description",
        "location",
        "license_plate",
        "vehicle_info",
        "user__username",
    )
    readonly_fields = (
        "created_at",
        "ai_processed_at",
        "ai_incident_type",
        "ai_nlp_confidence",
    )
    raw_id_fields = ("user", "citizen", "quartier")


admin.site.register(ReportAISettings)
admin.site.register(ScrapedReport)
