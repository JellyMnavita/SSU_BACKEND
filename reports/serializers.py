from rest_framework import serializers
from .models import Report
from users.models import User
from citizens.models import Citizen, CitizenAlternateData
from locations.models import Quartier
from rest_framework.exceptions import ValidationError
import json
from rest_framework.exceptions import ParseError

class ReportSerializer(serializers.ModelSerializer):
    # Champs personnalisés
    user_info = serializers.SerializerMethodField()
    citizen_info = serializers.SerializerMethodField()
    quartier_info = serializers.SerializerMethodField()
    citizen_data = serializers.DictField(write_only=True, required=False)

    # Affichages lisibles des choices
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    degree_display = serializers.CharField(source="get_degree_display", read_only=True)
    source_display = serializers.CharField(source="get_source_display", read_only=True)

    class Meta:
        model = Report
        fields = [
            "id",
            "description",
            "location",
            "longitude",
            "latitude",
            "degree",
            "degree_display",
            "status",
            "status_display",
            "picture",
            "source",
            "source_display",
            "created_at",
            "user",
            "user_info",
            "quartier",
            "quartier_info",
            "citizen",
            "citizen_info",
            "citizen_data",
        ]
        extra_kwargs = {
            "quartier": {"write_only": True},
            "citizen": {"write_only": True},
            "source": {"read_only": True},
            "user": {"read_only": True},
        }

    # Méthodes pour enrichir les infos retournées
    def get_user_info(self, obj):
        if obj.user:
            return {
                "id": obj.user.id,
                "username": obj.user.username,
                "type": obj.user.type_user.get_code_typeUser_display(),
            }
        return None

    def get_citizen_info(self, obj):
        if obj.citizen:
            return {
                "id": obj.citizen.id,
                "name": obj.citizen.name,
                "lastname": obj.citizen.lastname,
            }
        return None

    def get_quartier_info(self, obj):
        if obj.quartier:
            return {
                "id": obj.quartier.id,
                "nom": obj.quartier.nom,
                "commune": obj.quartier.commune.nom,
            }
        return None

    def validate_picture(self, value):
        # Validation de l'image
        if value.size > 5 * 1024 * 1024:  # 5MB
            raise serializers.ValidationError("La taille de l'image ne doit pas dépasser 5MB")
        if not value.name.lower().endswith(('.jpg', '.jpeg', '.png')):
            raise serializers.ValidationError("Format d'image non supporté")
        return value
    # Validation des données avant création
    def validate(self, data):
        user = self.context["request"].user if "request" in self.context else None
        citizen_data = self.initial_data.get("citizen_data", None)
        citizen_data_str = self.initial_data.get("citizen_data", None)
        if citizen_data_str:
            try:
                data['citizen_data'] = json.loads(citizen_data_str)
               
            except json.JSONDecodeError:
                raise ParseError("Format JSON invalide pour citizen_data")
            
        if user and user.is_authenticated:
            if user.type_user.code_typeUser not in ["ADMIN", "USER"]:
                raise ValidationError(
                    "Seuls les ADMIN et USER peuvent créer des reports"
                )
            data["user"] = user
            data["source"] = "U"  # Utilisateur inscrit
        elif citizen_data:
           
            required_fields = [
                "name",
                "lastname",
                "email",
                "birth_date",
                "nationality",
                "quartier",
            ]
            if not all(field in citizen_data for field in required_fields):
                raise ValidationError("Toutes les informations citoyen sont requises")
            data["source"] = "C"  # Citoyen anonyme
        else:
            raise ValidationError("Source non autorisée")

        # Validation des coordonnées GPS
        if not (-90 <= data["latitude"] <= 90) or not (
            -180 <= data["longitude"] <= 180
        ):
            raise ValidationError("Coordonnées GPS invalides")

        return data

    # Création du report et du citoyen si nécessaire
    def create(self, validated_data):
        citizen_data = validated_data.pop("citizen_data", None)
 
        if validated_data.get("source") == "C" and citizen_data:
            
            try:
                citizen_quartier = Quartier.objects.get(id=citizen_data["quartier"])
            except Quartier.DoesNotExist:
                raise serializers.ValidationError(
                    {"quartier": "Quartier invalide pour le citoyen"}
                )

            try:
                citizen = Citizen.objects.get(email=citizen_data["email"])
                differences = get_field_differences(
                    citizen, citizen_data, citizen_quartier
                )

                if differences:
                    CitizenAlternateData.objects.create(
                        citizen=citizen,
                        name=citizen_data["name"],
                        lastname=citizen_data["lastname"],
                        sexe=citizen_data.get("sexe", "M"),
                        nationality=citizen_data["nationality"],
                        profession=citizen_data.get("profession", ""),
                        civil_status=citizen_data.get("civil_status", "S"),
                        quartier=citizen_quartier,
                    )
            except Citizen.DoesNotExist:
                citizen = Citizen.objects.create(
                    name=citizen_data["name"],
                    lastname=citizen_data["lastname"],
                    email=citizen_data["email"],
                    birth_date=citizen_data["birth_date"],
                    nationality=citizen_data["nationality"],
                    quartier=citizen_quartier,
                    profession=citizen_data.get("profession", ""),
                    sexe=citizen_data.get("sexe", "M"),
                    civil_status=citizen_data.get("civil_status", "S"),
                )

            validated_data["citizen"] = citizen

        return super().create(validated_data)


def get_field_differences(citizen, new_data, quartier):
    fields = [
        "name",
        "lastname",
        "sexe",
        "nationality",
        "profession",
        "civil_status",
        "quartier",
    ]
    return {
        field: new_data.get(field)
        for field in fields
        if getattr(citizen, field)
        != (quartier if field == "quartier" else new_data.get(field))
    }


class ReportDetailsSerializer(serializers.ModelSerializer):
    quartier_info = serializers.SerializerMethodField()
    # Affichages lisibles des choices
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    degree_display = serializers.CharField(source="get_degree_display", read_only=True)
    source_display = serializers.CharField(source="get_source_display", read_only=True)

    class Meta:
        model = Report
        fields = [
            "description",
            "location",
            "degree_display",
            "status_display",
            "source_display",
            "quartier",
            "created_at",
            "quartier_info",
        ]
        extra_kwargs = {
            "quartier": {"write_only": True},
        }

    def get_quartier_info(self, obj):
        if obj.quartier:
            return {
                "id": obj.quartier.id,
                "nom": obj.quartier.nom,
                "commune": obj.quartier.commune.nom,
            }
        return None


class ReportStatusSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Report
        fields = ["id", "status", "status_display"]
