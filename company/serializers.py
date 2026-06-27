from rest_framework import serializers

from locations.kinshasa_bounds import assert_kinshasa_coordinates

from .models import CompanySite

MAX_SITES_PER_USER = 10


class CompanySiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanySite
        fields = [
            "id",
            "name",
            "commune",
            "address",
            "latitude",
            "longitude",
            "alert_radius_m",
            "site_type",
            "is_planned",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        lat = attrs.get("latitude", getattr(self.instance, "latitude", None))
        lng = attrs.get("longitude", getattr(self.instance, "longitude", None))
        if lat is not None and lng is not None:
            assert_kinshasa_coordinates(lat, lng)
        radius = attrs.get("alert_radius_m", getattr(self.instance, "alert_radius_m", 1000))
        if radius < 200 or radius > 10000:
            raise serializers.ValidationError(
                {"alert_radius_m": "Le rayon doit être entre 200 m et 10 km."}
            )
        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        count = CompanySite.objects.filter(user=user).count()
        if count >= MAX_SITES_PER_USER:
            raise serializers.ValidationError(
                f"Maximum {MAX_SITES_PER_USER} sites par organisation."
            )
        return CompanySite.objects.create(user=user, **validated_data)
