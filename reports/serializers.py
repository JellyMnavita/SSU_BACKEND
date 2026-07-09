from rest_framework import serializers
from .models import Report
from users.models import User
from citizens.models import Citizen, CitizenAlternateData
from locations.geo_validation import assert_report_coordinates
from locations.models import Quartier
from rest_framework.exceptions import ValidationError
import hashlib
import json
from rest_framework.exceptions import ParseError
from datetime import date
from common.i18n import validation_error, translate

def _parse_birth_date(value):
    if isinstance(value, date):
        return value
    if not value:
        raise ValidationError(translate("ERR_BIRTHDATE_REQUIRED"))
    try:
        # accepte 'YYYY-MM-DD'
        return date.fromisoformat(str(value))
    except Exception:
        raise ValidationError(translate("ERR_BIRTHDATE_FORMAT"))


def _validate_birth_date(birth_date: date) -> None:
    today = date.today()
    if birth_date > today:
        raise ValidationError(translate("ERR_BIRTHDATE_FUTURE"))
    age = today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )
    # bornes simples pour bloquer les valeurs absurdes
    if age < 13:
        raise ValidationError(translate("ERR_BIRTHDATE_TOO_YOUNG"))
    if age > 120:
        raise ValidationError(translate("ERR_BIRTHDATE_TOO_OLD"))

class ReportSerializer(serializers.ModelSerializer):
    # Champs personnalisés
    user_info = serializers.SerializerMethodField()
    citizen_info = serializers.SerializerMethodField()
    quartier_info = serializers.SerializerMethodField()
    citizen_data = serializers.JSONField(write_only=True, required=False)

    # Affichages lisibles des choices
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    degree_display = serializers.CharField(source="get_degree_display", read_only=True)
    source_display = serializers.CharField(source="get_source_display", read_only=True)
    ai_processing_status_display = serializers.CharField(
        source="get_ai_processing_status_display", read_only=True
    )
    ai_moderation_recommendation_display = serializers.SerializerMethodField()
    picture_url = serializers.SerializerMethodField()

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
            "picture_url",
            "picture_sha256",
            "source",
            "source_display",
            "incident_type",
            "vehicle_info",
            "direction",
            "license_plate",
            "is_anonymous",
            "is_witness",
            "mobile_local_id",
            "created_at",
            "user",
            "user_info",
            "quartier",
            "quartier_info",
            "citizen",
            "citizen_info",
            "citizen_data",
            "ai_incident_type",
            "ai_nlp_confidence",
            "ai_vision_results",
            "user_degree_before_ai",
            "ai_recommended_degree",
            "degree_adjusted_by_ai",
            "ai_processing_status",
            "ai_processing_status_display",
            "ai_processing_errors",
            "ai_processed_at",
            "ai_moderation_recommendation",
            "ai_moderation_recommendation_display",
            "ai_moderation_confidence",
            "ai_moderation_reasons",
            "ai_enrichment_summary",
            "ai_moderation_auto_applied",
            "external_source_url",
            "incident_type",
            "vehicle_info",
            "direction",
            "license_plate",
            "is_anonymous",
            "is_witness",
        ]
        extra_kwargs = {
            "quartier": {"write_only": True},
            "citizen": {"write_only": True},
            "picture": {"required": False, "allow_null": True},
            "picture_sha256": {"read_only": True},
            "source": {"read_only": True},
            "user": {"read_only": True},
            "user_degree_before_ai": {"read_only": True},
            "ai_recommended_degree": {"read_only": True},
            "degree_adjusted_by_ai": {"read_only": True},
            "ai_processing_status": {"read_only": True},
            "ai_processing_errors": {"read_only": True},
            "ai_processed_at": {"read_only": True},
            "ai_moderation_recommendation": {"read_only": True},
            "ai_moderation_confidence": {"read_only": True},
            "ai_moderation_reasons": {"read_only": True},
            "ai_enrichment_summary": {"read_only": True},
            "ai_moderation_auto_applied": {"read_only": True},
        }

    def get_ai_moderation_recommendation_display(self, obj):
        labels = {"V": "Valider", "R": "Rejeter", "P": "En attente"}
        if not obj.ai_moderation_recommendation:
            return None
        return labels.get(obj.ai_moderation_recommendation, obj.ai_moderation_recommendation)

    def get_picture_url(self, obj):
        if not obj.picture:
            return None
        return obj.picture.url

    # Méthodes pour enrichir les infos retournées
    def get_user_info(self, obj):
        if obj.user:
            return {
                "id": obj.user.id,
                "username": obj.user.username,
                "email": obj.user.email,
                "type": obj.user.type_user.get_code_typeUser_display(),
            }
        return None

    def get_citizen_info(self, obj):
        if obj.citizen:
            return {
                "id": obj.citizen.id,
                "name": obj.citizen.name,
                "lastname": obj.citizen.lastname,
                "email": obj.citizen.email,
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
        if value is None:
            return value
        if value.size > 5 * 1024 * 1024:
            raise validation_error("ERR_IMAGE_TOO_LARGE", self.context)
        if not value.name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            raise validation_error("ERR_IMAGE_FORMAT", self.context)
        value.seek(0)
        digest = hashlib.sha256(value.read()).hexdigest()
        value.seek(0)
        self._pending_picture_sha256 = digest
        qs = Report.objects.filter(picture_sha256=digest)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise validation_error("ERR_IMAGE_DUPLICATE", self.context)
        return value

    def validate(self, data):
        # Mise à jour partielle (ex. statut admin) : pas de règles de création
        if self.instance is not None:
            latitude = data.get("latitude", self.instance.latitude)
            longitude = data.get("longitude", self.instance.longitude)
            location = data.get("location", self.instance.location)
            if latitude is not None and longitude is not None:
                if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                    raise ValidationError(translate("ERR_INVALID_GPS"))
                assert_report_coordinates(
                    latitude,
                    longitude,
                    location=location,
                )
            return data

        # Validation des données avant création
        user = self.context["request"].user if "request" in self.context else None
        citizen_data = data.get("citizen_data") or self.initial_data.get("citizen_data")
        if isinstance(citizen_data, str) and citizen_data.strip():
            try:
                citizen_data = json.loads(citizen_data)
            except json.JSONDecodeError:
                raise ParseError(translate("ERR_INVALID_JSON"))
        if citizen_data:
            data["citizen_data"] = citizen_data

        if user and user.is_authenticated:
            if user.type_user.code_typeUser not in ["ADMIN", "USER"]:
                raise ValidationError(translate("ERR_REPORT_ROLE_ONLY"))
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
                raise ValidationError(translate("ERR_CITIZEN_INFO_REQUIRED"))
            # Validation date de naissance (bloque future/absurde)
            citizen_data["birth_date"] = _parse_birth_date(citizen_data.get("birth_date"))
            _validate_birth_date(citizen_data["birth_date"])
            data["source"] = "C"  # Citoyen anonyme
        else:
            raise ValidationError(translate("ERR_SOURCE_NOT_ALLOWED"))

        if not (-90 <= data["latitude"] <= 90) or not (
            -180 <= data["longitude"] <= 180
        ):
            raise ValidationError(translate("ERR_INVALID_GPS"))

        assert_report_coordinates(
            data["latitude"],
            data["longitude"],
            location=data.get("location"),
        )

        # Le quartier du formulaire citoyen = domicile, pas le lieu du signalement.
        if data.get("source") == "C":
            data.pop("quartier", None)

        digest = getattr(self, "_pending_picture_sha256", None)
        if digest:
            data["picture_sha256"] = digest

        return data

    # Création du report et du citoyen si nécessaire
    def create(self, validated_data):
        citizen_data = validated_data.pop("citizen_data", None)
 
        if validated_data.get("source") == "C" and citizen_data:
            
            try:
                citizen_quartier = Quartier.objects.get(id=citizen_data["quartier"])
            except Quartier.DoesNotExist:
                raise validation_error("ERR_INVALID_QUARTIER", self.context, field="quartier")

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
    picture_url = serializers.SerializerMethodField()
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
            "picture",
            "picture_url",
            "quartier",
            "created_at",
            "quartier_info",
            "ai_incident_type",
            "ai_nlp_confidence",
            "ai_vision_results",
            "user_degree_before_ai",
            "ai_recommended_degree",
            "degree_adjusted_by_ai",
            "ai_processing_status",
            "ai_processing_errors",
            "ai_processed_at",
            "ai_moderation_recommendation",
            "ai_moderation_confidence",
            "ai_moderation_reasons",
            "ai_enrichment_summary",
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

    def get_picture_url(self, obj):
        if not obj.picture:
            return None
        return obj.picture.url


class ReportStatusSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Report
        fields = ["id", "status", "status_display"]


class UserReportUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ["description", "location", "degree", "latitude", "longitude"]

    def validate(self, data):
        instance = self.instance
        if instance and instance.status == "V":
            raise ValidationError(translate("ERR_VERIFIED_REPORT_LOCKED"))

        latitude = data.get("latitude", getattr(instance, "latitude", None))
        longitude = data.get("longitude", getattr(instance, "longitude", None))
        location = data.get("location", getattr(instance, "location", None))

        if latitude is not None and longitude is not None:
            assert_report_coordinates(
                latitude,
                longitude,
                location=location,
            )
        return data

    def update(self, instance, validated_data):
        if instance.status == "R":
            instance.status = "P"
        return super().update(instance, validated_data)


class AdminReportEditSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    degree_display = serializers.CharField(source="get_degree_display", read_only=True)

    class Meta:
        model = Report
        fields = [
            "id",
            "description",
            "location",
            "degree",
            "degree_display",
            "latitude",
            "longitude",
            "status",
            "status_display",
        ]

    def validate(self, data):
        instance = self.instance
        latitude = data.get("latitude", instance.latitude)
        longitude = data.get("longitude", instance.longitude)
        location = data.get("location", instance.location)

        if latitude is not None and longitude is not None:
            assert_report_coordinates(
                latitude,
                longitude,
                location=location,
            )
        return data


class ReportNotificationSerializer(serializers.ModelSerializer):
    report_id = serializers.IntegerField(source="report.id", read_only=True)

    class Meta:
        from .models import ReportNotification

        model = ReportNotification
        fields = ["id", "report_id", "status", "message", "read_at", "created_at"]
        read_only_fields = fields
