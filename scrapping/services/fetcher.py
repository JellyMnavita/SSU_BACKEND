"""Récupération des articles via scraping-service."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ai_gateway.clients.scraping import ScrapingServiceClient

logger = logging.getLogger(__name__)


@dataclass
class RawArticle:
    title: str
    link: str
    image: str | None
    date_label: str
    source_site: str
    content: str = ""


def _client() -> ScrapingServiceClient:
    return ScrapingServiceClient()


def _article_from_dict(data: dict) -> RawArticle:
    return RawArticle(
        title=data["title"],
        link=data["link"],
        image=data.get("image"),
        date_label=data.get("date_label", ""),
        source_site=data["source_site"],
        content=data.get("content", ""),
    )


def fetch_all_articles(fetch_body: bool = False) -> list[RawArticle]:
    payload = _client().scrape(fetch_body=fetch_body)
    return [_article_from_dict(item) for item in payload.get("articles", [])]


def articles_for_news_api() -> list[dict]:
    """Format léger pour la page Actualités (sans corps complet)."""
    return _client().news_feed()


def list_news_sources() -> list[dict]:
    """Sources configurées dans scraping-service."""
    return _client().list_sources()
