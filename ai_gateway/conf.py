import os


def _env_bool(name: str, default: bool = True) -> bool:
    return os.getenv(name, str(default)).lower() in ("1", "true", "yes", "on")


AI_GATEWAY_ENABLED = _env_bool("AI_GATEWAY_ENABLED", True)
AI_USE_MICROSERVICES = _env_bool("AI_USE_MICROSERVICES", True)

PREDICTION_SERVICE_URL = os.getenv(
    "PREDICTION_SERVICE_URL", "http://prediction-service:8001"
).rstrip("/")
NLP_SERVICE_URL = os.getenv("NLP_SERVICE_URL", "http://nlp-service:8002").rstrip("/")
VISION_SERVICE_URL = os.getenv(
    "VISION_SERVICE_URL", "http://vision-service:8003"
).rstrip("/")
SCRAPING_SERVICE_URL = os.getenv(
    "SCRAPING_SERVICE_URL", "http://scraping-service:8004"
).rstrip("/")

AI_HTTP_TIMEOUT = float(os.getenv("AI_HTTP_TIMEOUT", "15"))
PREDICTION_GRID_TIMEOUT = float(os.getenv("PREDICTION_GRID_TIMEOUT", "90"))
VISION_HTTP_TIMEOUT = float(os.getenv("VISION_HTTP_TIMEOUT", "90"))
SCRAPING_HTTP_TIMEOUT = float(os.getenv("SCRAPING_HTTP_TIMEOUT", "120"))
PREDICTION_TRAIN_TIMEOUT = float(os.getenv("PREDICTION_TRAIN_TIMEOUT", "180"))
AI_HTTP_RETRIES = int(os.getenv("AI_HTTP_RETRIES", "2"))
AI_HTTP_RETRY_BACKOFF = float(os.getenv("AI_HTTP_RETRY_BACKOFF", "0.5"))
