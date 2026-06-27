from rest_framework import serializers

from .models import Citizen, CitizenAlternateData


class CitizenAlternateDataSerializer(serializers.ModelSerializer):
    quartier_name = serializers.CharField(source="quartier.nom", read_only=True)
    commune_name = serializers.CharField(source="quartier.commune.nom", read_only=True)

    class Meta:
        model = CitizenAlternateData
        fields = [
            "id",
            "name",
            "lastname",
            "sexe",
            "nationality",
            "profession",
            "civil_status",
            "quartier",
            "quartier_name",
            "commune_name",
            "created_at",
        ]


class CitizenSerializer(serializers.ModelSerializer):
    quartier_name = serializers.CharField(source="quartier.nom", read_only=True)
    commune_name = serializers.CharField(source="quartier.commune.nom", read_only=True)
    alternate_data = CitizenAlternateDataSerializer(many=True, read_only=True)

    class Meta:
        model = Citizen
        fields = [
            "id",
            "name",
            "lastname",
            "email",
            "sexe",
            "birth_date",
            "nationality",
            "profession",
            "civil_status",
            "quartier",
            "quartier_name",
            "commune_name",
            "created_at",
            "alternate_data",
        ]
