from django.conf import settings

from .base import BaseAIServiceClient


class ScrapingServiceClient(BaseAIServiceClient):
    service_name = "scraping-service"

    def __init__(self, base_url: str | None = None):
        super().__init__(base_url or settings.SCRAPING_SERVICE_URL)
        self.timeout = getattr(settings, "SCRAPING_HTTP_TIMEOUT", 120.0)

    def list_sources(self) -> list[dict]:
        return self._request("GET", "/sources")

    def scrape(self, *, fetch_body: bool = False, source_id: str | None = None) -> dict:
        return self._request(
            "POST",
            "/scrape",
            json={"fetch_body": fetch_body, "source_id": source_id},
        )

    def news_feed(self) -> list[dict]:
        return self._request("GET", "/articles/news-feed")
