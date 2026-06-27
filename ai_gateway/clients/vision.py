import mimetypes

from django.conf import settings

from .base import BaseAIServiceClient


def _image_mime_type(filename: str) -> str:
    mime, _ = mimetypes.guess_type(filename)
    if mime and mime.startswith("image/"):
        return mime
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
        "gif": "image/gif",
        "bmp": "image/bmp",
    }.get(ext, "image/jpeg")


class VisionServiceClient(BaseAIServiceClient):
    service_name = "vision-service"

    def __init__(self, base_url: str | None = None):
        super().__init__(base_url or settings.VISION_SERVICE_URL)

    def analyze_image(self, file_bytes: bytes, filename: str = "image.jpg") -> dict:
        content_type = _image_mime_type(filename)
        files = {"file": (filename, file_bytes, content_type)}
        vision_timeout = float(getattr(settings, "VISION_HTTP_TIMEOUT", 90))
        return self._request("POST", "/analyze-image", files=files, timeout=vision_timeout)

    def train(self, timeout: float | None = 30.0) -> dict:
        return self._request("POST", "/train", timeout=timeout)

    def train_status(self) -> dict:
        return self._request("GET", "/train/status", timeout=15.0)
