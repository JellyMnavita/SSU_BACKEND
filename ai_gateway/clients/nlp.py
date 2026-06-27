from django.conf import settings

from .base import BaseAIServiceClient


class NLPServiceClient(BaseAIServiceClient):
    service_name = "nlp-service"

    def __init__(self, base_url: str | None = None):
        super().__init__(base_url or settings.NLP_SERVICE_URL)

    def classify_text(self, text: str) -> dict:
        return self._request("POST", "/classify-text", json={"text": text})

    def train(
        self,
        samples: list[dict],
        epochs: int = 8,
        *,
        use_corpus: bool = False,
        train_camembert: bool = False,
    ) -> dict:
        train_timeout = getattr(settings, "AI_TRAIN_TIMEOUT", 1800.0)
        return self._request(
            "POST",
            "/train",
            json={
                "samples": samples,
                "epochs": epochs,
                "use_corpus": use_corpus,
                "train_camembert": train_camembert,
            },
            timeout=train_timeout,
        )

    def health(self) -> dict:
        return self._request("GET", "/health")
