from django.conf import settings

from .base import BaseAIServiceClient


class PredictionServiceClient(BaseAIServiceClient):
    service_name = "prediction-service"

    def __init__(self, base_url: str | None = None):
        super().__init__(base_url or settings.PREDICTION_SERVICE_URL)

    def predict(
        self,
        latitude: float,
        longitude: float,
        *,
        density: float | None = None,
        mean_degree_danger: float | None = None,
        hour: int = 14,
        day_of_week: int = 2,
    ) -> dict:
        payload = {
            "latitude": latitude,
            "longitude": longitude,
            "hour": hour,
            "day_of_week": day_of_week,
        }
        if density is not None:
            payload["density"] = density
        if mean_degree_danger is not None:
            payload["mean_degree_danger"] = mean_degree_danger
        return self._request("POST", "/predict", json=payload)

    def get_grid_layers(
        self,
        *,
        hour: int = 14,
        day_of_week: int = 2,
        grid_size: int = 48,
        include_sectors: bool = True,
    ) -> dict:
        timeout = getattr(settings, "PREDICTION_GRID_TIMEOUT", 90.0)
        return self._request(
            "GET",
            "/grid/layers",
            params={
                "hour": hour,
                "day_of_week": day_of_week,
                "grid_size": grid_size,
                "sectors": 1 if include_sectors else 0,
            },
            timeout=timeout,
        )

    def score_routes(self, payload: dict) -> dict:
        timeout = getattr(settings, "PREDICTION_GRID_TIMEOUT", 90.0)
        return self._request("POST", "/routes/score", json=payload, timeout=timeout)

    def train(self) -> dict:
        self.timeout = getattr(settings, "PREDICTION_TRAIN_TIMEOUT", 180.0)
        return self._request("POST", "/train")

    def reload(self) -> dict:
        return self._request("POST", "/reload")
