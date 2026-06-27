"""Client HTTP résilient pour les microservices IA."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class AIServiceError(Exception):
    """Erreur d'appel à un microservice IA."""

    def __init__(self, service: str, message: str, status_code: int | None = None):
        self.service = service
        self.status_code = status_code
        super().__init__(f"[{service}] {message}")


class BaseAIServiceClient:
    service_name: str = "ai-service"

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.timeout = getattr(settings, "AI_HTTP_TIMEOUT", 15.0)
        self.retries = getattr(settings, "AI_HTTP_RETRIES", 2)
        self.retry_backoff = getattr(settings, "AI_HTTP_RETRY_BACKOFF", 0.5)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        files: dict | None = None,
        params: dict | None = None,
        timeout: float | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        last_error: Exception | None = None
        request_timeout = timeout if timeout is not None else self.timeout

        for attempt in range(self.retries + 1):
            try:
                with httpx.Client(timeout=request_timeout) as client:
                    response = client.request(
                        method,
                        url,
                        json=json,
                        files=files,
                        params=params,
                    )
                if response.status_code >= 400:
                    raise AIServiceError(
                        self.service_name,
                        response.text[:500],
                        status_code=response.status_code,
                    )
                if response.headers.get("content-type", "").startswith("application/json"):
                    return response.json()
                return response.content
            except (httpx.RequestError, AIServiceError) as exc:
                last_error = exc
                logger.warning(
                    "%s %s attempt %s/%s failed: %s",
                    self.service_name,
                    path,
                    attempt + 1,
                    self.retries + 1,
                    exc,
                )
                if attempt < self.retries:
                    time.sleep(self.retry_backoff * (attempt + 1))

        raise AIServiceError(
            self.service_name,
            str(last_error) if last_error else "unknown error",
        )

    def health(self) -> dict:
        return self._request("GET", "/health")
