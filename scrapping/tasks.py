from celery import shared_task
import requests
from bs4 import BeautifulSoup
from django.core.cache import cache
from .serializers import ScrappingSerializer
import logging

URL = "https://congorassure.cd/index.php/securite"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@shared_task
def refresh_scrapping_cache():
    logger.info("### DÉBUT TÂCHE ###")
    print("Tâche exécutée !")  # Visible dans la console
  
    try:
        response = requests.get(URL, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        return

    soup = BeautifulSoup(response.text, "html.parser")
    articles = []
    for article in soup.find_all("div", class_="views-field views-field-nothing"):
        title_tag = article.find("h1")
        title = title_tag.find("a").text.strip() if title_tag and title_tag.find("a") else "Titre inconnu"
        link = "https://congorassure.cd" + title_tag.find("a")["href"] if title_tag and title_tag.find("a") else "#"
        image_tag = article.find("img")
        image = image_tag["src"] if image_tag and "src" in image_tag.attrs else None
        if image and not image.startswith("http"):
            image = "https://congorassure.cd" + image
        date_tag = article.find("time")
        date = date_tag.text.strip() if date_tag else "Date inconnue"
        articles.append({
            "title": title,
            "link": link,
            "image": image,
            "date": date
        })
    serializer = ScrappingSerializer(articles, many=True)
    cache.set("scrapping_articles", serializer.data, timeout=60*10)  # 10 minutes
    # Votre logique ici...
    logger.info("### FIN TÂCHE ###")