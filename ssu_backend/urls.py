from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve

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

# En DEBUG, helper Django ; en prod, servir aussi via gunicorn en secours
# (nginx doit servir /media depuis le volume — voir ssu_frontend_safe/nginx.conf).
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += [
        re_path(
            r"^media/(?P<path>.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]

