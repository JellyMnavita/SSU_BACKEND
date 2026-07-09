from rest_framework import serializers

from common.i18n import validation_error, translate

from .models import ReportAISettings


class ReportAISettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportAISettings
        fields = [
            "auto_apply_moderation",
            "auto_reject_enabled",
            "auto_reject_citizen_reports",
            "auto_reject_score_threshold",
            "auto_ingest_news",
            "auto_vision_retrain_weekly",
            "vision_retrain_after_exports",
            "public_map_retention_days",
            "accent_theme",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]

    def validate_accent_theme(self, value):
        allowed = {c[0] for c in ReportAISettings.ACCENT_THEME_CHOICES}
        if value not in allowed:
            raise validation_error(
                "ERR_INVALID_THEME",
                self.context,
                values=", ".join(sorted(allowed)),
            )
        return value

    def validate_auto_reject_score_threshold(self, value):
        if value is None:
            return value
        if not 0.0 <= float(value) <= 1.0:
            raise validation_error("ERR_THRESHOLD_RANGE", self.context)
        return float(value)

    def validate_vision_retrain_after_exports(self, value):
        if value is None:
            return 0
        return max(0, int(value))

    def validate_public_map_retention_days(self, value):
        if value is None:
            return 30
        return max(0, min(int(value), 365))
