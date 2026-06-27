from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from scrapping.services.fetcher import articles_for_news_api


class GetScrappingView(APIView):
    def get(self, request):
        cached_data = cache.get("scrapping_articles")
        if cached_data:
            return Response(cached_data)

        try:
            articles = articles_for_news_api()
        except Exception as e:
            return Response(
                {"error": f"Impossible d'accéder aux sources d'actualités: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if not articles:
            return Response(
                {"error": "Aucun article trouvé"},
                status=status.HTTP_404_NOT_FOUND,
            )

        cache.set("scrapping_articles", articles, timeout=60 * 30)
        return Response(articles)
