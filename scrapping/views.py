from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import requests
from bs4 import BeautifulSoup
from .serializers import ScrappingSerializer

URL = "https://congorassure.cd/index.php/securite"

class GetScrappingView(APIView):
    def get(self, request):
        try:
            response = requests.get(URL, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            return Response(
                {"error": f"Impossible d'accéder au site: {e}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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

        if not articles:
            return Response(
                {"error": "Aucun article trouvé"}, 
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ScrappingSerializer(articles, many=True)
        return Response(serializer.data)
