from datetime import datetime

from django.conf import settings
from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from ai_gateway.clients import PredictionServiceClient
from ai_gateway.clients.base import AIServiceError

from .grid_utils import build_commune_risk_summary
from .serializers import SafeRouteRequestSerializer

PREDICTION_LEVEL_MAP = {"safe": 0, "moderate": 1, "dangerous": 2}
LABEL_DISPLAY = {0: "faible", 1: "modéré", 2: "élevé"}


def _prediction_client() -> PredictionServiceClient:
    return PredictionServiceClient()


def _service_required() -> bool:
    return getattr(settings, "AI_GATEWAY_ENABLED", True)


class DangerPredictionProximityAPIView(APIView):
    """Carte 48×48 — inférence déléguée à prediction-service."""

    def get(self, request):
        if not _service_required():
            return Response(
                {"error": "prediction-service requis (AI_GATEWAY_ENABLED=1)"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            hour = int(request.GET.get("hour", 14))
            day_of_week = int(request.GET.get("day_of_week", 2))
            include_sectors = request.GET.get("sectors", "1") != "0"

            cache_key = f"prediction_layers:{hour}:{day_of_week}:{include_sectors}"
            cached_result = cache.get(cache_key)
            if cached_result:
                return Response(cached_result)

            client = _prediction_client()
            layers = client.get_grid_layers(
                hour=hour,
                day_of_week=day_of_week,
                include_sectors=include_sectors,
            )
            communes = build_commune_risk_summary()

            payload = {
                **layers,
                "meta": {
                    **layers.get("meta", {}),
                    "commune_count": len(communes),
                },
                "communes": communes,
            }

            cache.set(cache_key, payload, timeout=60 * 10)
            return Response(payload)

        except AIServiceError as exc:
            return Response(
                {"error": str(exc), "service": "prediction-service"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DangerPredictSingleAPIView(APIView):
    """Prédiction ponctuelle — prediction-service."""

    def get(self, request):
        if not _service_required():
            return Response(
                {"error": "prediction-service requis (AI_GATEWAY_ENABLED=1)"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            lat = float(request.GET.get("latitude"))
            lon = float(request.GET.get("longitude"))
            hour = int(request.GET.get("hour"))
            day_of_week = int(request.GET.get("day_of_week"))

            cache_key = f"prediction:{lat}:{lon}:{hour}:{day_of_week}"
            cached_result = cache.get(cache_key)
            if cached_result:
                return Response(cached_result)

            ms = _prediction_client().predict(
                latitude=lat,
                longitude=lon,
                hour=hour,
                day_of_week=day_of_week,
            )
            prediction = ms.get("prediction_int")
            if prediction is None:
                prediction = PREDICTION_LEVEL_MAP.get(ms["prediction"], 1)

            result = {
                "latitude": lat,
                "longitude": lon,
                "hour": hour,
                "day_of_week": day_of_week,
                "density": ms.get("density"),
                "mean_degree_danger": ms.get("mean_degree_danger"),
                "prediction": prediction,
                "label": LABEL_DISPLAY.get(prediction, ms.get("label", "modéré")),
                "confidence": ms.get("confidence"),
                "risk_score": ms.get("risk_score"),
                "probabilities": ms.get("probabilities", {}),
                "proba_0": ms.get("proba_0"),
                "proba_1": ms.get("proba_1"),
                "proba_2": ms.get("proba_2"),
                "source": "prediction-service",
            }

            cache.set(cache_key, result, timeout=60 * 10)
            return Response(result)

        except AIServiceError as exc:
            return Response(
                {"error": str(exc), "service": "prediction-service"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SafeRouteScoreAPIView(APIView):
    """Scoring d'itinéraires — prediction-service."""

    def post(self, request):
        if not _service_required():
            return Response(
                {"error": "prediction-service requis (AI_GATEWAY_ENABLED=1)"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        serializer = SafeRouteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payload = serializer.validated_data
        now = datetime.now()
        hour = payload.get("hour", now.hour)
        day_of_week = payload.get("day_of_week", now.weekday())

        try:
            ms_payload = {
                "origin": payload["origin"],
                "destination": payload["destination"],
                "hour": hour,
                "day_of_week": day_of_week,
                "routes": payload["routes"],
            }
            return Response(_prediction_client().score_routes(ms_payload))
        except AIServiceError as exc:
            return Response(
                {"error": str(exc), "service": "prediction-service"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
