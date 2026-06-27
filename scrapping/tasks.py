import logging

from celery import shared_task
from django.core.cache import cache

from scrapping.services.fetcher import articles_for_news_api
from scrapping.services.ingest import run_news_ingest

logger = logging.getLogger(__name__)


@shared_task(name="scrapping.tasks.refresh_scrapping_cache")
def refresh_scrapping_cache():
    """Met à jour le cache de la page Actualités."""
    logger.info("Rafraîchissement cache actualités")
    try:
        articles = articles_for_news_api()
        cache.set("scrapping_articles", articles, timeout=60 * 30)
        logger.info("%s article(s) en cache", len(articles))
    except Exception:
        logger.exception("Échec refresh_scrapping_cache")


@shared_task(name="scrapping.tasks.ingest_security_news")
def ingest_security_news(max_articles: int = 50):
    """Scrape les sites d'actualité et crée des signalements source=S."""
    logger.info("Début ingestion actualités sécurité")
    stats = run_news_ingest(max_articles=max_articles)
    logger.info("Ingestion terminée: %s", stats)
    refresh_scrapping_cache.delay()
    return stats
