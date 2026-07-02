from rest_framework import serializers

from .models import PolicePost


class PolicePostPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicePost
        fields = [
            "id",
            "name",
            "commune",
            "address",
            "latitude",
            "longitude",
            "post_type",
        ]


class PolicePostSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicePost
        fields = [
            "id",
            "name",
            "commune",
            "address",
            "latitude",
            "longitude",
            "patrol_radius_m",
            "post_type",
            "contact_phone",
            "officers_count",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)
