from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("users.urls")),  # Ajoute les routes de l'API utilisateur
    path("api/", include("locations.urls")),  # Ajoute les routes de l'API location
    path("api/", include("reports.urls")),  # Ajoute les routes de l'API location
    path("api/", include("citizens.urls")),
    path("api/", include("scrapping.urls")),  # Ajoute les routes de l'API scrapping
    path("api/", include("prediction.urls")),  # Ajoute les routes de l'API prediction
    path("api/", include("safety.urls")),
    path("api/", include("company.urls")),
    path("api/", include("gov.urls")),
    path("api/", include("police.urls")),
]


urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

