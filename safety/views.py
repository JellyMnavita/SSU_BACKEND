import uuid
from datetime import timedelta

from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError

from common.i18n import translate
from rest_framework.response import Response
from rest_framework.views import APIView

from reports.models import Report
from reports.tasks import process_report_ai
from django.conf import settings
from users.permissions import IsAdminOrGov, IsAdminUserType
from users.account_tiers import MinCitizenTierPermission, PRO

from .models import CheckIn, SafetyAlert, TrackingPoint, TrackingSession, Trip, TrustedContact
from .serializers import (
    CheckInMissedSerializer,
    CheckInSerializer,
    CheckInStartSerializer,
    EmergencyAlertSerializer,
    MobileBatchSyncSerializer,
    SafetyAlertSerializer,
    TrackingPointCreateSerializer,
    TrackingSessionSerializer,
    TripSerializer,
    TripStartSerializer,
    TrustedContactSerializer,
)
from .notify import (
    notify_checkin_contacts,
    notify_checkin_missed_contacts,
    notify_sos_contacts,
    notify_trip_contacts,
)
from .services import map_mobile_degree, map_mobile_source, user_can_trigger_sos
from .sos_report import finalize_sos_report, is_sos_report


MAX_TRUSTED_CONTACTS = 5
KINSHASA_DEFAULT_LAT = -4.4419
KINSHASA_DEFAULT_LNG = 15.3276


class IsAuthenticatedUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.type_user.code_typeUser in ["USER", "ADMIN"]
        )


def _create_emergency_report(user, *, kind, lat, lng, location, description, mobile_local_id=None):
    source = "O" if kind == "sos" else "Q"
    default_desc = (
        "SOS — signalement d'urgence automatique."
        if kind == "sos"
        else "Signalement rapide — double appui volume (mobile Bokengi)."
    )
    report = Report.objects.create(
        user=user,
        description=description or default_desc,
        location=location or f"Coordonnées ({lat:.5f}, {lng:.5f})",
        longitude=lng,
        latitude=lat,
        degree="E",
        source=source,
        incident_type="autre",
        mobile_local_id=mobile_local_id,
        ai_processing_status="pending",
    )
    if kind == "sos":
        finalize_sos_report(report)
    elif getattr(settings, "AI_GATEWAY_ENABLED", True):
        process_report_ai.delay(report.id)
    return report


def _start_tracking(user, *, kind, lat, lng, report=None, share_interval_min=2, mobile_local_id=None):
    token = uuid.uuid4().hex[:12]
    now = timezone.now()
    return TrackingSession.objects.create(
        user=user,
        token=token,
        kind=kind,
        status="active",
        share_interval_min=share_interval_min,
        last_latitude=lat,
        last_longitude=lng,
        last_shared_at=now,
        report=report,
        mobile_local_id=mobile_local_id,
        started_at=now,
    )


class TrustedContactListCreateView(generics.ListCreateAPIView):
    serializer_class = TrustedContactSerializer
    permission_classes = [IsAuthenticatedUser, MinCitizenTierPermission]
    min_citizen_tier = PRO

    def get_queryset(self):
        return TrustedContact.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        count = TrustedContact.objects.filter(user=self.request.user).count()
        if count >= MAX_TRUSTED_CONTACTS:
            raise ValidationError(
                translate("ERR_MAX_TRUSTED_CONTACTS", max=MAX_TRUSTED_CONTACTS)
            )
        serializer.save(user=self.request.user)


class TrustedContactDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TrustedContactSerializer
    permission_classes = [IsAuthenticatedUser, MinCitizenTierPermission]
    min_citizen_tier = PRO

    def get_queryset(self):
        return TrustedContact.objects.filter(user=self.request.user)


class EmergencyAlertView(APIView):
    """SOS ou signalement rapide + session de suivi GPS."""

    permission_classes = [IsAuthenticatedUser]

    def post(self, request):
        ser = EmergencyAlertSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        user = request.user

        if data["kind"] == "sos" and not user_can_trigger_sos(user):
            return Response(
                {"detail": "Le SOS est réservé aux citoyens Premium."},
                status=status.HTTP_403_FORBIDDEN,
            )

        contact_ids = data.get("contact_ids") or []
        if data["kind"] == "sos":
            if contact_ids:
                valid_ids = set(
                    TrustedContact.objects.filter(
                        user=user, id__in=contact_ids
                    ).values_list("id", flat=True)
                )
                contact_ids = [cid for cid in contact_ids if cid in valid_ids]
            else:
                contact_ids = list(
                    TrustedContact.objects.filter(user=user).values_list("id", flat=True)
                )

        report = _create_emergency_report(
            user,
            kind=data["kind"],
            lat=data["latitude"],
            lng=data["longitude"],
            location=data.get("location", ""),
            description=data.get("description", ""),
            mobile_local_id=data.get("mobile_local_id"),
        )
        session = _start_tracking(
            user,
            kind=data["kind"],
            lat=data["latitude"],
            lng=data["longitude"],
            report=report,
            share_interval_min=data.get("share_interval_min", 2),
            mobile_local_id=data.get("mobile_local_id"),
        )
        TrackingPoint.objects.create(
            session=session,
            latitude=data["latitude"],
            longitude=data["longitude"],
            recorded_at=timezone.now(),
        )

        notify_stats = None
        if data["kind"] == "sos" and contact_ids:
            notify_stats = notify_sos_contacts(session, contact_ids)

        return Response(
            {
                "report_id": report.id,
                "session": TrackingSessionSerializer(session).data,
                "maps_link": f"https://maps.google.com/?q={data['latitude']},{data['longitude']}",
                "track_url": f"/suivi/{session.token}",
                "contacts_notified": notify_stats["in_app"] + notify_stats["email"] if notify_stats else 0,
                "notification_stats": notify_stats,
                "message": "Alerte enregistrée — suivi GPS actif.",
            },
            status=status.HTTP_201_CREATED,
        )


class TrackingSessionStopView(APIView):
    permission_classes = [IsAuthenticatedUser]

    def post(self, request, token):
        try:
            session = TrackingSession.objects.get(
                token=token, user=request.user, status="active"
            )
        except TrackingSession.DoesNotExist:
            return Response({"error": "Session introuvable."}, status=404)

        session.status = "completed"
        session.ended_at = timezone.now()
        session.save(update_fields=["status", "ended_at"])
        return Response(TrackingSessionSerializer(session).data)


class TrackingPointCreateView(APIView):
    permission_classes = [IsAuthenticatedUser]

    def post(self, request, token):
        try:
            session = TrackingSession.objects.get(token=token, user=request.user)
        except TrackingSession.DoesNotExist:
            return Response({"error": "Session introuvable."}, status=404)

        ser = TrackingPointCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        recorded_at = data.get("recorded_at") or timezone.now()

        point = TrackingPoint.objects.create(
            session=session,
            latitude=data["latitude"],
            longitude=data["longitude"],
            recorded_at=recorded_at,
        )
        session.last_latitude = data["latitude"]
        session.last_longitude = data["longitude"]
        session.last_shared_at = recorded_at
        session.save(update_fields=["last_latitude", "last_longitude", "last_shared_at"])

        return Response(
            {
                "point_id": point.id,
                "maps_link": f"https://maps.google.com/?q={data['latitude']},{data['longitude']}",
            },
            status=status.HTTP_201_CREATED,
        )


class TrackingSessionLiveView(generics.RetrieveAPIView):
    """Consultation publique du suivi via token (lien partagé)."""

    serializer_class = TrackingSessionSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "token"

    def get_queryset(self):
        return TrackingSession.objects.prefetch_related("points").select_related(
            "user", "report"
        )


class TripStartView(APIView):
    permission_classes = [IsAuthenticatedUser, MinCitizenTierPermission]
    min_citizen_tier = PRO

    def post(self, request):
        ser = TripStartSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        user = request.user

        contact_ids = data.get("contact_ids") or []
        valid_ids = set(
            TrustedContact.objects.filter(user=user, id__in=contact_ids).values_list(
                "id", flat=True
            )
        )
        contact_ids = [cid for cid in contact_ids if cid in valid_ids]
        contact = None
        if contact_ids:
            contact = TrustedContact.objects.filter(user=user, id=contact_ids[0]).first()

        session = _start_tracking(
            user,
            kind="trip",
            lat=data["origin_lat"],
            lng=data["origin_lng"],
            share_interval_min=data.get("share_interval_min", 2),
        )
        trip = Trip.objects.create(
            user=user,
            tracking_session=session,
            contact=contact,
            origin_lat=data["origin_lat"],
            origin_lng=data["origin_lng"],
            origin_label=data.get("origin_label", ""),
            dest_lat=data["dest_lat"],
            dest_lng=data["dest_lng"],
            dest_label=data.get("dest_label", ""),
            estimated_minutes=data["estimated_minutes"],
            mobile_local_id=data.get("mobile_local_id"),
            started_at=timezone.now(),
        )
        TrackingPoint.objects.create(
            session=session,
            latitude=data["origin_lat"],
            longitude=data["origin_lng"],
            recorded_at=timezone.now(),
        )

        notify_stats = None
        if contact_ids:
            notify_stats = notify_trip_contacts(
                session,
                contact_ids,
                dest_label=data.get("dest_label", ""),
            )

        return Response(
            {
                "trip": TripSerializer(trip).data,
                "session": TrackingSessionSerializer(session).data,
                "contacts_notified": notify_stats["in_app"] + notify_stats["email"]
                if notify_stats
                else 0,
                "notification_stats": notify_stats,
                "message": "Trajet partagé — suivi GPS actif.",
            },
            status=status.HTTP_201_CREATED,
        )


class TripStopView(APIView):
    permission_classes = [IsAuthenticatedUser, MinCitizenTierPermission]
    min_citizen_tier = PRO

    def post(self, request, pk):
        try:
            trip = Trip.objects.get(pk=pk, user=request.user, status="active")
        except Trip.DoesNotExist:
            return Response({"error": "Trajet introuvable."}, status=404)

        trip.status = "completed"
        trip.ended_at = timezone.now()
        trip.save(update_fields=["status", "ended_at"])

        if trip.tracking_session and trip.tracking_session.status == "active":
            trip.tracking_session.status = "completed"
            trip.tracking_session.ended_at = timezone.now()
            trip.tracking_session.save(update_fields=["status", "ended_at"])

        return Response(TripSerializer(trip).data)


class CheckInStartView(APIView):
    permission_classes = [IsAuthenticatedUser, MinCitizenTierPermission]
    min_citizen_tier = PRO

    def post(self, request):
        ser = CheckInStartSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        user = request.user
        now = timezone.now()

        contact_ids = data.get("contact_ids") or []
        valid_ids = set(
            TrustedContact.objects.filter(user=user, id__in=contact_ids).values_list(
                "id", flat=True
            )
        )
        contact_ids = [cid for cid in contact_ids if cid in valid_ids]

        lat = data.get("latitude") if data.get("latitude") is not None else KINSHASA_DEFAULT_LAT
        lng = data.get("longitude") if data.get("longitude") is not None else KINSHASA_DEFAULT_LNG

        session = _start_tracking(
            user,
            kind="checkin",
            lat=lat,
            lng=lng,
            share_interval_min=data.get("share_interval_min", 2),
            mobile_local_id=data.get("mobile_local_id"),
        )
        TrackingPoint.objects.create(
            session=session,
            latitude=lat,
            longitude=lng,
            recorded_at=now,
        )

        check_in = CheckIn.objects.create(
            user=user,
            duration_minutes=data["duration_minutes"],
            due_at=now + timedelta(minutes=data["duration_minutes"]),
            status="pending",
            auto_sos=data.get("auto_sos", True),
            contact_ids=contact_ids,
            tracking_session=session,
            mobile_local_id=data.get("mobile_local_id"),
        )

        notify_stats = None
        if contact_ids:
            notify_stats = notify_checkin_contacts(
                session,
                contact_ids,
                duration_minutes=data["duration_minutes"],
            )

        return Response(
            {
                "check_in": CheckInSerializer(check_in).data,
                "session": TrackingSessionSerializer(session).data,
                "contacts_notified": notify_stats["in_app"] + notify_stats["email"]
                if notify_stats
                else 0,
                "notification_stats": notify_stats,
                "message": "Check-in actif — confirmez avant l'échéance.",
            },
            status=status.HTTP_201_CREATED,
        )


class CheckInConfirmView(APIView):
    permission_classes = [IsAuthenticatedUser, MinCitizenTierPermission]
    min_citizen_tier = PRO

    def post(self, request, pk):
        try:
            check_in = CheckIn.objects.select_related("tracking_session").get(
                pk=pk, user=request.user, status="pending"
            )
        except CheckIn.DoesNotExist:
            return Response({"error": "Check-in introuvable."}, status=404)

        check_in.status = "confirmed"
        check_in.confirmed_at = timezone.now()
        check_in.save(update_fields=["status", "confirmed_at"])

        session = check_in.tracking_session
        if session and session.status == "active":
            session.status = "completed"
            session.ended_at = timezone.now()
            session.save(update_fields=["status", "ended_at"])

        return Response(CheckInSerializer(check_in).data)


class CheckInMissedView(APIView):
    """Escalade client lorsque le délai est écoulé sans confirmation."""

    permission_classes = [IsAuthenticatedUser, MinCitizenTierPermission]
    min_citizen_tier = PRO

    def post(self, request, pk):
        ser = CheckInMissedSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        try:
            check_in = CheckIn.objects.select_related("tracking_session").get(
                pk=pk, user=request.user, status="pending"
            )
        except CheckIn.DoesNotExist:
            return Response({"error": "Check-in introuvable."}, status=404)

        if timezone.now() < check_in.due_at:
            return Response(
                {"error": "Le délai n'est pas encore écoulé."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        check_in.status = "missed"
        check_in.save(update_fields=["status"])

        user = request.user
        contact_ids = list(check_in.contact_ids or [])
        session = check_in.tracking_session
        notify_stats = None
        sos_triggered = False

        if session:
            lat = data.get("latitude")
            lng = data.get("longitude")
            if lat is not None and lng is not None:
                session.last_latitude = lat
                session.last_longitude = lng
                session.last_shared_at = timezone.now()
                session.save(
                    update_fields=["last_latitude", "last_longitude", "last_shared_at"]
                )
                TrackingPoint.objects.create(
                    session=session,
                    latitude=lat,
                    longitude=lng,
                    recorded_at=timezone.now(),
                )

            if contact_ids:
                notify_stats = notify_checkin_missed_contacts(session, contact_ids)

            if check_in.auto_sos and user_can_trigger_sos(user):
                lat = session.last_latitude or KINSHASA_DEFAULT_LAT
                lng = session.last_longitude or KINSHASA_DEFAULT_LNG
                report = _create_emergency_report(
                    user,
                    kind="sos",
                    lat=lat,
                    lng=lng,
                    location="",
                    description="SOS automatique — check-in non confirmé.",
                    mobile_local_id=check_in.mobile_local_id,
                )
                session.report = report
                session.kind = "sos"
                session.save(update_fields=["report", "kind"])
                if contact_ids:
                    notify_sos_contacts(session, contact_ids)
                sos_triggered = True
            elif session.status == "active":
                session.status = "completed"
                session.ended_at = timezone.now()
                session.save(update_fields=["status", "ended_at"])

        return Response(
            {
                "check_in": CheckInSerializer(check_in).data,
                "contacts_notified": notify_stats["in_app"] + notify_stats["email"]
                if notify_stats
                else 0,
                "notification_stats": notify_stats,
                "sos_triggered": sos_triggered,
                "message": "Check-in manqué — contacts alertés."
                if notify_stats
                else "Check-in manqué.",
            }
        )


class MobileBatchSyncView(APIView):
    """Sync batch depuis Bokengi (SQLite → PostgreSQL)."""

    permission_classes = [IsAuthenticatedUser]

    def post(self, request):
        ser = MobileBatchSyncSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        user = request.user

        id_maps = {
            "reports": {},
            "trusted_contacts": {},
            "tracking_sessions": {},
            "trips": {},
            "check_ins": {},
        }

        for item in data.get("trusted_contacts", []):
            obj, _ = TrustedContact.objects.update_or_create(
                user=user,
                mobile_local_id=item["mobile_local_id"],
                defaults={
                    "name": item["name"],
                    "phone": item["phone"],
                    "email": item.get("email", ""),
                    "relationship": item.get("relationship", ""),
                },
            )
            id_maps["trusted_contacts"][item["mobile_local_id"]] = obj.id

        for item in data.get("reports", []):
            source = map_mobile_source(
                item.get("source", "citizen"),
                is_witness=item.get("is_witness", False),
                is_sos=item.get("source", "").lower() == "sos",
            )
            if source == "O" and not user_can_trigger_sos(user):
                continue

            report, created = Report.objects.update_or_create(
                user=user,
                mobile_local_id=item["mobile_local_id"],
                defaults={
                    "description": item["description"],
                    "location": item["location"],
                    "longitude": item["longitude"],
                    "latitude": item["latitude"],
                    "degree": map_mobile_degree(item["degree"]),
                    "source": source,
                    "incident_type": item.get("incident_type", "autre"),
                    "vehicle_info": item.get("vehicle_info", ""),
                    "direction": item.get("direction", ""),
                    "license_plate": item.get("license_plate", ""),
                    "is_anonymous": item.get("is_anonymous", False),
                    "is_witness": item.get("is_witness", False),
                },
            )
            if is_sos_report(report):
                finalize_sos_report(report)
            elif created and getattr(settings, "AI_GATEWAY_ENABLED", True):
                report.ai_processing_status = "pending"
                report.save(update_fields=["ai_processing_status"])
                process_report_ai.delay(report.id)
            id_maps["reports"][item["mobile_local_id"]] = report.id

        for item in data.get("tracking_sessions", []):
            report = None
            rml = item.get("report_mobile_local_id")
            if rml and rml in id_maps["reports"]:
                report = Report.objects.filter(id=id_maps["reports"][rml]).first()

            session, _ = TrackingSession.objects.update_or_create(
                user=user,
                mobile_local_id=item["mobile_local_id"],
                defaults={
                    "token": item["token"],
                    "kind": item["kind"],
                    "status": item.get("status", "active"),
                    "share_interval_min": item.get("share_interval_min", 2),
                    "last_latitude": item.get("last_latitude"),
                    "last_longitude": item.get("last_longitude"),
                    "last_shared_at": item.get("last_shared_at"),
                    "started_at": item["started_at"],
                    "ended_at": item.get("ended_at"),
                    "report": report,
                },
            )
            id_maps["tracking_sessions"][item["mobile_local_id"]] = session.id

        for item in data.get("tracking_points", []):
            session_id = id_maps["tracking_sessions"].get(
                item["session_mobile_local_id"]
            )
            if not session_id:
                continue
            session = TrackingSession.objects.filter(id=session_id).first()
            if not session:
                continue
            TrackingPoint.objects.get_or_create(
                session=session,
                latitude=item["latitude"],
                longitude=item["longitude"],
                recorded_at=item["recorded_at"],
            )

        for item in data.get("trips", []):
            session = None
            sml = item.get("tracking_session_mobile_local_id")
            if sml and sml in id_maps["tracking_sessions"]:
                session = TrackingSession.objects.filter(
                    id=id_maps["tracking_sessions"][sml]
                ).first()
            contact = None
            cml = item.get("contact_mobile_local_id")
            if cml and cml in id_maps["trusted_contacts"]:
                contact = TrustedContact.objects.filter(
                    id=id_maps["trusted_contacts"][cml]
                ).first()

            trip, _ = Trip.objects.update_or_create(
                user=user,
                mobile_local_id=item["mobile_local_id"],
                defaults={
                    "tracking_session": session,
                    "contact": contact,
                    "origin_lat": item["origin_lat"],
                    "origin_lng": item["origin_lng"],
                    "origin_label": item.get("origin_label", ""),
                    "dest_lat": item["dest_lat"],
                    "dest_lng": item["dest_lng"],
                    "dest_label": item.get("dest_label", ""),
                    "estimated_minutes": item["estimated_minutes"],
                    "status": item.get("status", "active"),
                    "alert_reason": item.get("alert_reason", ""),
                    "started_at": item["started_at"],
                    "ended_at": item.get("ended_at"),
                },
            )
            id_maps["trips"][item["mobile_local_id"]] = trip.id

        for item in data.get("check_ins", []):
            session = None
            sml = item.get("tracking_session_mobile_local_id")
            if sml and sml in id_maps["tracking_sessions"]:
                session = TrackingSession.objects.filter(
                    id=id_maps["tracking_sessions"][sml]
                ).first()

            check_in, _ = CheckIn.objects.update_or_create(
                user=user,
                mobile_local_id=item["mobile_local_id"],
                defaults={
                    "duration_minutes": item["duration_minutes"],
                    "due_at": item["due_at"],
                    "confirmed_at": item.get("confirmed_at"),
                    "status": item.get("status", "pending"),
                    "auto_sos": item.get("auto_sos", True),
                    "contact_ids": item.get("contact_ids", []),
                    "tracking_session": session,
                },
            )
            id_maps["check_ins"][item["mobile_local_id"]] = check_in.id

        return Response(
            {
                "synced": True,
                "id_maps": id_maps,
                "message": "Synchronisation batch terminée.",
            },
            status=status.HTTP_200_OK,
        )


class SafetyAlertListView(generics.ListAPIView):
    """Alertes SOS reçues par le citoyen connecté."""

    serializer_class = SafetyAlertSerializer
    permission_classes = [IsAuthenticatedUser]

    def get_queryset(self):
        return (
            SafetyAlert.objects.filter(recipient=self.request.user)
            .select_related("initiator", "tracking_session")
            .order_by("-created_at")[:100]
        )


class SafetyAlertMarkReadView(APIView):
    permission_classes = [IsAuthenticatedUser]

    def post(self, request, pk):
        try:
            alert = SafetyAlert.objects.get(pk=pk, recipient=request.user)
        except SafetyAlert.DoesNotExist:
            return Response({"error": "Alerte introuvable."}, status=404)
        if not alert.read_at:
            alert.read_at = timezone.now()
            alert.save(update_fields=["read_at"])
        return Response(SafetyAlertSerializer(alert).data)


class SafetyAlertDeleteView(APIView):
    """Supprime une alerte SOS reçue (masquage côté destinataire)."""

    permission_classes = [IsAuthenticatedUser]

    def delete(self, request, pk):
        deleted, _ = SafetyAlert.objects.filter(pk=pk, recipient=request.user).delete()
        if not deleted:
            return Response({"error": "Alerte introuvable."}, status=404)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SafetyAlertClearView(APIView):
    """Supprime toutes les alertes SOS reçues par l'utilisateur connecté."""

    permission_classes = [IsAuthenticatedUser]

    def delete(self, request):
        count, _ = SafetyAlert.objects.filter(recipient=request.user).delete()
        return Response({"deleted": count}, status=status.HTTP_200_OK)


class SafetyAlertUnreadCountView(APIView):
    """Nombre d'alertes SOS non lues pour le citoyen connecté."""

    permission_classes = [IsAuthenticatedUser]

    def get(self, request):
        count = SafetyAlert.objects.filter(
            recipient=request.user,
            read_at__isnull=True,
        ).count()
        return Response({"unread_count": count})


class AdminSafetyDashboardView(APIView):
    """Vue admin : sessions actives + alertes récentes."""

    permission_classes = [IsAdminOrGov]

    def get(self, request):
        active_sessions = TrackingSession.objects.filter(status="active").select_related(
            "user"
        )[:50]
        active_trips = Trip.objects.filter(status="active").select_related("user")[:50]
        pending_checkins = CheckIn.objects.filter(status="pending")[:50]
        emergency_reports = Report.objects.filter(source__in=["O", "Q", "W"]).order_by(
            "-created_at"
        )[:30]

        return Response(
            {
                "active_tracking_sessions": TrackingSessionSerializer(
                    active_sessions, many=True
                ).data,
                "active_trips": TripSerializer(active_trips, many=True).data,
                "pending_check_ins": CheckInSerializer(pending_checkins, many=True).data,
                "recent_emergency_reports": [
                    {
                        "id": r.id,
                        "source": r.get_source_display(),
                        "location": r.location,
                        "latitude": r.latitude,
                        "longitude": r.longitude,
                        "created_at": r.created_at,
                        "user": r.user.username if r.user else None,
                    }
                    for r in emergency_reports
                ],
            }
        )
