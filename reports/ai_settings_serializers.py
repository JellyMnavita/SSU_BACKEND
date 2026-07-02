from rest_framework import serializers

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
            "updated_at",
        ]
        read_only_fields = ["updated_at"]

    def validate_auto_reject_score_threshold(self, value):
        if value is None:
            return value
        if not 0.0 <= float(value) <= 1.0:
            raise serializers.ValidationError("Le seuil doit être entre 0 et 1.")
        return float(value)

    def validate_vision_retrain_after_exports(self, value):
        if value is None:
            return 0
        return max(0, int(value))

    def validate_public_map_retention_days(self, value):
        if value is None:
            return 30
        return max(0, min(int(value), 365))
