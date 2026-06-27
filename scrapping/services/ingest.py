"""Ingestion actualités → ScrapedReport + Report (source=S) + IA."""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from reports.cache_utils import invalidate_reports_list_cache
from reports.models import Report, ReportAISettings, ScrapedReport
from reports.tasks import process_report_ai
from scrapping.services.fetcher import RawArticle, fetch_all_articles
from scrapping.services.geocoder import geocode_kinshasa
from scrapping.services.images import download_article_image
from scrapping.services.security_filter import (
    build_description,
    explain_geo_rejection,
    explain_institutional_rejection,
    explain_outside_kinshasa_incident,
    explain_security_rejection,
    incident_location_outside_kinshasa,
    is_institutional_news,
    is_security_related,
    mentions_kinshasa,
)

logger = logging.getLogger(__name__)


def ingest_enabled() -> bool:
    if not getattr(settings, "NEWS_INGEST_ENABLED", True):
        return False
    return ReportAISettings.get_solo().auto_ingest_news


def _reject_scraped(url: str, title: str, reason: str, **extra) -> None:
    ScrapedReport.objects.update_or_create(
        url_source=url,
        defaults={
            "title": title[:300],
            "content": extra.get("content", ""),
            "status": "R",
            "reject_reason": reason,
            "source_site": extra.get("source_site", ""),
            "published_label": extra.get("published_label", ""),
            "image_url": extra.get("image_url", ""),
        },
    )


@transaction.atomic
def _process_article(article: RawArticle) -> str:
    """
    Retourne: created | skipped | rejected | exists
    """
    if ScrapedReport.objects.filter(url_source=article.link).exists():
        return "exists"

    full_text = f"{article.title}\n{article.content}"
    if is_institutional_news(full_text):
        _reject_scraped(
            article.link,
            article.title,
            explain_institutional_rejection(full_text),
            content=article.content,
            source_site=article.source_site,
            published_label=article.date_label,
            image_url=article.image or "",
        )
        return "rejected"

    if not is_security_related(full_text):
        _reject_scraped(
            article.link,
            article.title,
            explain_security_rejection(full_text),
            content=article.content,
            source_site=article.source_site,
            published_label=article.date_label,
            image_url=article.image or "",
        )
        return "rejected"

    outside, outside_region = incident_location_outside_kinshasa(
        article.title, article.content
    )
    if outside:
        _reject_scraped(
            article.link,
            article.title,
            explain_outside_kinshasa_incident(outside_region, article.title),
            content=article.content,
            source_site=article.source_site,
            published_label=article.date_label,
            image_url=article.image or "",
        )
        return "rejected"

    geo = geocode_kinshasa(full_text)
    if not geo and not mentions_kinshasa(full_text):
        _reject_scraped(
            article.link,
            article.title,
            explain_geo_rejection(full_text),
            content=article.content,
            source_site=article.source_site,
            published_label=article.date_label,
            image_url=article.image or "",
        )
        return "rejected"

    if not geo:
        from scrapping.services.geocoder import KINSHASA_CENTER

        lat, lon = KINSHASA_CENTER
        location = "Kinshasa (localisation estimée), RDC"
        quartier = None
    else:
        lat = geo["latitude"]
        lon = geo["longitude"]
        location = geo["location"]
        quartier = geo.get("quartier")

    description = build_description(article.title, article.content)
    picture = download_article_image(
        article.image,
        fallback_name=f"news_{abs(hash(article.link)) % 10**8}",
    )

    scraped = ScrapedReport.objects.create(
        url_source=article.link,
        title=article.title[:300],
        content=article.content,
        image_url=article.image or "",
        source_site=article.source_site,
        published_label=article.date_label,
        latitude=lat,
        longitude=lon,
        location_label=location,
        status="P",
    )

    report = Report.objects.create(
        description=description,
        location=location,
        latitude=lat,
        longitude=lon,
        degree="M",
        picture=picture,
        status="P",
        source="S",
        user=None,
        citizen=None,
        quartier=quartier,
        external_source_url=article.link,
        ai_processing_status="pending",
    )

    scraped.report = report
    scraped.status = "T"
    scraped.save(update_fields=["report", "status"])

    if getattr(settings, "AI_GATEWAY_ENABLED", True):
        process_report_ai.delay(report.id)
    else:
        report.ai_processing_status = "skipped"
        report.save(update_fields=["ai_processing_status"])

    invalidate_reports_list_cache()
    logger.info("Signalement système créé #%s depuis %s", report.id, article.link)
    return "created"


def run_news_ingest(max_articles: int = 50, force: bool = False) -> dict:
    """
    Scrape les sources, filtre, géolocalise et crée des signalements source=S.
    """
    if not force and not ingest_enabled():
        return {
            "enabled": False,
            "message": "Ingestion actualités désactivée (paramètre admin ou NEWS_INGEST_ENABLED).",
        }

    articles = fetch_all_articles(fetch_body=True)
    existing_urls = set(
        ScrapedReport.objects.values_list("url_source", flat=True)
    )
    # Traiter d'abord les articles jamais vus
    ordered = sorted(
        articles,
        key=lambda a: (a.link in existing_urls, a.link),
    )

    stats = {
        "enabled": True,
        "fetched": len(articles),
        "evaluated": 0,
        "not_evaluated": 0,
        "created": 0,
        "rejected": 0,
        "skipped": 0,
        "exists": 0,
    }

    for article in ordered:
        if stats["evaluated"] >= max_articles:
            break
        try:
            result = _process_article(article)
            stats["evaluated"] += 1
            stats[result] = stats.get(result, 0) + 1
        except Exception:
            logger.exception("Échec ingestion article %s", article.link)
            stats["evaluated"] += 1
            stats["skipped"] = stats.get("skipped", 0) + 1

    stats["not_evaluated"] = max(0, len(articles) - stats["evaluated"])
    stats["finished_at"] = timezone.now().isoformat()
    cache.set("ingest:last_run", stats, timeout=60 * 60 * 24)
    return stats
