from rest_framework import serializers

from locations.kinshasa_bounds import assert_kinshasa_coordinates

from .models import CheckIn, SafetyAlert, TrackingPoint, TrackingSession, Trip, TrustedContact


def _validate_kin_pair(latitude: float, longitude: float) -> None:
    assert_kinshasa_coordinates(latitude, longitude)


class TrustedContactSerializer(serializers.ModelSerializer):
    telegram_linked = serializers.SerializerMethodField()

    class Meta:
        model = TrustedContact
        fields = [
            "id",
            "name",
            "phone",
            "email",
            "relationship",
            "telegram_linked",
            "mobile_local_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "telegram_linked", "created_at", "updated_at"]

    def get_telegram_linked(self, obj: TrustedContact) -> bool:
        return bool(obj.telegram_chat_id)


class TrackingPointSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrackingPoint
        fields = ["id", "latitude", "longitude", "recorded_at"]
        read_only_fields = ["id"]


class TrackingSessionSerializer(serializers.ModelSerializer):
    points = TrackingPointSerializer(many=True, read_only=True)
    maps_link = serializers.SerializerMethodField()
    initiator_name = serializers.SerializerMethodField()
    initiator_sex = serializers.SerializerMethodField()

    class Meta:
        model = TrackingSession
        fields = [
            "id",
            "token",
            "kind",
            "status",
            "share_interval_min",
            "last_latitude",
            "last_longitude",
            "last_shared_at",
            "report",
            "mobile_local_id",
            "started_at",
            "ended_at",
            "created_at",
            "points",
            "maps_link",
            "initiator_name",
            "initiator_sex",
        ]
        read_only_fields = [
            "id",
            "token",
            "created_at",
            "points",
            "maps_link",
            "initiator_name",
            "initiator_sex",
        ]

    def get_initiator_name(self, obj):
        user = getattr(obj, "user", None)
        if not user:
            return None
        return user.username or user.email or "Citoyen"

    def get_initiator_sex(self, obj):
        user = getattr(obj, "user", None)
        if not user:
            return None
        sex = (getattr(user, "sexe_user", None) or "").strip().upper()
        return "F" if sex == "F" else "M"

    def get_maps_link(self, obj):
        if obj.last_latitude is None or obj.last_longitude is None:
            return None
        return f"https://maps.google.com/?q={obj.last_latitude},{obj.last_longitude}"


class TripSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip
        fields = [
            "id",
            "tracking_session",
            "contact",
            "origin_lat",
            "origin_lng",
            "origin_label",
            "dest_lat",
            "dest_lng",
            "dest_label",
            "estimated_minutes",
            "status",
            "alert_reason",
            "mobile_local_id",
            "started_at",
            "ended_at",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class CheckInSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheckIn
        fields = [
            "id",
            "duration_minutes",
            "due_at",
            "confirmed_at",
            "status",
            "auto_sos",
            "contact_ids",
            "tracking_session",
            "mobile_local_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class EmergencyAlertSerializer(serializers.Serializer):
    """SOS ou signalement rapide depuis mobile."""

    kind = serializers.ChoiceField(choices=["sos", "quick"])
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    location = serializers.CharField(max_length=200, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    share_interval_min = serializers.IntegerField(default=2, min_value=1, max_value=30)
    mobile_local_id = serializers.IntegerField(required=False, allow_null=True)
    contact_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
    )

    def validate(self, attrs):
        _validate_kin_pair(attrs["latitude"], attrs["longitude"])
        return attrs


class SafetyAlertSerializer(serializers.ModelSerializer):
    initiator_name = serializers.SerializerMethodField()
    tracking_token = serializers.SerializerMethodField()
    maps_link = serializers.SerializerMethodField()

    class Meta:
        model = SafetyAlert
        fields = [
            "id",
            "kind",
            "message",
            "read_at",
            "created_at",
            "initiator_name",
            "tracking_token",
            "maps_link",
        ]
        read_only_fields = fields

    def get_initiator_name(self, obj):
        user = obj.initiator
        return user.username or user.email or "Un proche"

    def get_tracking_token(self, obj):
        session = obj.tracking_session
        return session.token if session else None

    def get_maps_link(self, obj):
        session = obj.tracking_session
        if not session or session.last_latitude is None or session.last_longitude is None:
            return None
        return (
            f"https://maps.google.com/?q={session.last_latitude},{session.last_longitude}"
        )


class TripStartSerializer(serializers.Serializer):
    origin_lat = serializers.FloatField()
    origin_lng = serializers.FloatField()
    origin_label = serializers.CharField(required=False, allow_blank=True, default="")
    dest_lat = serializers.FloatField()
    dest_lng = serializers.FloatField()
    dest_label = serializers.CharField(required=False, allow_blank=True, default="")
    estimated_minutes = serializers.IntegerField(min_value=5, max_value=360)
    contact_id = serializers.IntegerField(required=False, allow_null=True)
    contact_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )
    share_interval_min = serializers.IntegerField(default=2, min_value=1, max_value=30)
    mobile_local_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        _validate_kin_pair(attrs["origin_lat"], attrs["origin_lng"])
        _validate_kin_pair(attrs["dest_lat"], attrs["dest_lng"])
        ids = list(attrs.get("contact_ids") or [])
        if attrs.get("contact_id"):
            ids.append(attrs["contact_id"])
        attrs["contact_ids"] = list(dict.fromkeys(ids))
        return attrs


class CheckInStartSerializer(serializers.Serializer):
    duration_minutes = serializers.IntegerField(min_value=5, max_value=120)
    auto_sos = serializers.BooleanField(default=True)
    contact_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )
    mobile_local_id = serializers.IntegerField(required=False, allow_null=True)
    latitude = serializers.FloatField(required=False, allow_null=True)
    longitude = serializers.FloatField(required=False, allow_null=True)
    share_interval_min = serializers.IntegerField(default=2, min_value=1, max_value=30)

    def validate(self, attrs):
        lat = attrs.get("latitude")
        lng = attrs.get("longitude")
        if lat is not None and lng is not None:
            _validate_kin_pair(lat, lng)
        return attrs


class CheckInMissedSerializer(serializers.Serializer):
    latitude = serializers.FloatField(required=False, allow_null=True)
    longitude = serializers.FloatField(required=False, allow_null=True)

    def validate(self, attrs):
        lat = attrs.get("latitude")
        lng = attrs.get("longitude")
        if lat is not None and lng is not None:
            _validate_kin_pair(lat, lng)
        return attrs


class TrackingPointCreateSerializer(serializers.Serializer):
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    recorded_at = serializers.DateTimeField(required=False)

    def validate(self, attrs):
        _validate_kin_pair(attrs["latitude"], attrs["longitude"])
        return attrs


class MobileReportSyncSerializer(serializers.Serializer):
    mobile_local_id = serializers.IntegerField()
    description = serializers.CharField()
    location = serializers.CharField()
    longitude = serializers.FloatField()
    latitude = serializers.FloatField()
    degree = serializers.CharField()
    source = serializers.CharField(required=False, default="citizen")
    incident_type = serializers.CharField(required=False, default="autre")
    vehicle_info = serializers.CharField(required=False, allow_blank=True, default="")
    direction = serializers.CharField(required=False, allow_blank=True, default="")
    license_plate = serializers.CharField(required=False, allow_blank=True, default="")
    is_anonymous = serializers.BooleanField(default=False)
    is_witness = serializers.BooleanField(default=False)
    created_at = serializers.DateTimeField(required=False)

    def validate(self, attrs):
        _validate_kin_pair(attrs["latitude"], attrs["longitude"])
        return attrs


class MobileTrustedContactSyncSerializer(serializers.Serializer):
    mobile_local_id = serializers.IntegerField()
    name = serializers.CharField()
    phone = serializers.CharField()
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    relationship = serializers.CharField(required=False, allow_blank=True, default="")
    created_at = serializers.DateTimeField(required=False)


class MobileTrackingSessionSyncSerializer(serializers.Serializer):
    mobile_local_id = serializers.IntegerField()
    token = serializers.CharField()
    kind = serializers.CharField()
    status = serializers.CharField(default="active")
    share_interval_min = serializers.IntegerField(default=2)
    last_latitude = serializers.FloatField(required=False, allow_null=True)
    last_longitude = serializers.FloatField(required=False, allow_null=True)
    last_shared_at = serializers.DateTimeField(required=False, allow_null=True)
    started_at = serializers.DateTimeField()
    ended_at = serializers.DateTimeField(required=False, allow_null=True)
    report_mobile_local_id = serializers.IntegerField(required=False, allow_null=True)


class MobileTrackingPointSyncSerializer(serializers.Serializer):
    session_mobile_local_id = serializers.IntegerField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    recorded_at = serializers.DateTimeField()


class MobileTripSyncSerializer(serializers.Serializer):
    mobile_local_id = serializers.IntegerField()
    tracking_session_mobile_local_id = serializers.IntegerField(required=False, allow_null=True)
    contact_mobile_local_id = serializers.IntegerField(required=False, allow_null=True)
    origin_lat = serializers.FloatField()
    origin_lng = serializers.FloatField()
    origin_label = serializers.CharField(required=False, allow_blank=True, default="")
    dest_lat = serializers.FloatField()
    dest_lng = serializers.FloatField()
    dest_label = serializers.CharField(required=False, allow_blank=True, default="")
    estimated_minutes = serializers.IntegerField()
    status = serializers.CharField(default="active")
    alert_reason = serializers.CharField(required=False, allow_blank=True, default="")
    started_at = serializers.DateTimeField()
    ended_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, attrs):
        _validate_kin_pair(attrs["origin_lat"], attrs["origin_lng"])
        _validate_kin_pair(attrs["dest_lat"], attrs["dest_lng"])
        return attrs


class MobileCheckInSyncSerializer(serializers.Serializer):
    mobile_local_id = serializers.IntegerField()
    duration_minutes = serializers.IntegerField()
    due_at = serializers.DateTimeField()
    confirmed_at = serializers.DateTimeField(required=False, allow_null=True)
    status = serializers.CharField(default="pending")
    auto_sos = serializers.BooleanField(default=True)
    contact_ids = serializers.ListField(child=serializers.IntegerField(), default=list)
    tracking_session_mobile_local_id = serializers.IntegerField(required=False, allow_null=True)


class MobileBatchSyncSerializer(serializers.Serializer):
    reports = MobileReportSyncSerializer(many=True, required=False, default=list)
    trusted_contacts = MobileTrustedContactSyncSerializer(
        many=True, required=False, default=list
    )
    tracking_sessions = MobileTrackingSessionSyncSerializer(
        many=True, required=False, default=list
    )
    tracking_points = MobileTrackingPointSyncSerializer(
        many=True, required=False, default=list
    )
    trips = MobileTripSyncSerializer(many=True, required=False, default=list)
    check_ins = MobileCheckInSyncSerializer(many=True, required=False, default=list)
