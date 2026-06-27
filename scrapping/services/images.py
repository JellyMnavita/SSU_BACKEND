"""Téléchargement d'images pour signalements système."""

from __future__ import annotations

import base64
import logging
from io import BytesIO

import requests
from django.core.files.base import ContentFile

from scrapping.services.sources import USER_AGENT

logger = logging.getLogger(__name__)

_PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def placeholder_image(name: str = "news_placeholder.png") -> ContentFile:
    return ContentFile(_PLACEHOLDER_PNG, name=name)


def download_article_image(url: str | None, fallback_name: str) -> ContentFile:
    if not url:
        return placeholder_image(fallback_name)

    try:
        resp = requests.get(
            url,
            timeout=20,
            headers={"User-Agent": USER_AGENT},
            stream=True,
        )
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if "image" not in content_type and not url.lower().endswith(
            (".jpg", ".jpeg", ".png", ".webp")
        ):
            return placeholder_image(fallback_name)

        data = resp.content
        if len(data) < 100 or len(data) > 5 * 1024 * 1024:
            return placeholder_image(fallback_name)

        ext = ".jpg"
        if "png" in content_type or url.lower().endswith(".png"):
            ext = ".png"
        elif "webp" in content_type:
            ext = ".webp"
        return ContentFile(BytesIO(data).read(), name=f"{fallback_name}{ext}")
    except Exception as exc:
        logger.warning("Image non téléchargée %s: %s", url, exc)
        return placeholder_image(fallback_name)
