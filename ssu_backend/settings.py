from pathlib import Path
import os
from datetime import timedelta
from dotenv import load_dotenv
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG", "False") == "True"   

def _split_env_list(value):
    return [item.strip() for item in value.split(",") if item.strip()]


def _host_only(value):
    return value.replace("http://", "").replace("https://", "").split("/")[0]


ALLOWED_HOSTS = _split_env_list(os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,192.168.101.120,192.168.101.122"))
ALLOWED_HOSTS = [_host_only(host) for host in ALLOWED_HOSTS]

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "users",
    "citizens",
    "reports",
    "locations",
    "scrapping",
    "prediction",
    "ai_gateway",
    "safety",
    "company",
    "gov",
    "police",
    "rest_framework",
    'rest_framework.authtoken',
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
]

# Celery/django_celery_beat est optionnel selon l'environnement.
try:
    import django_celery_beat  # noqa: F401

    INSTALLED_APPS.append("django_celery_beat")
except ModuleNotFoundError:
    pass

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "common.middleware.LanguageMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "users.middleware.UserActivityMiddleware",
]

ROOT_URLCONF = "ssu_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "ssu_backend.wsgi.application"


# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT"),
    }
}

# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = "fr"
TIME_ZONE = "Africa/Kinshasa"

USE_I18N = True
USE_L10N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = "static/"

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "users.User"

# Configuration SMTP pour l'envoi d'emails
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
EMAIL_SUBJECT_PREFIX = ""
_server_user = (EMAIL_HOST_USER or "").strip()
_app_name = os.getenv("APP_NAME", "SSU Bokengi")
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    f"{_app_name} <{_server_user}>" if _server_user else _app_name,
)
SERVER_EMAIL = DEFAULT_FROM_EMAIL
APP_NAME = _app_name
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL") or _server_user
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
}


SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=3),
    "ROTATE_REFRESH_TOKENS": True,  # Crée un nouveau refresh token à chaque rafraîchissement
    "BLACKLIST_AFTER_ROTATION": True,  # Rend l'ancien refresh token inutilisable
    "UPDATE_LAST_LOGIN": True,  # Met à jour last_login dans le modèle User
}

# URL de votre frontend pour le lien de reset
FRONTEND_URL = os.getenv("FRONTEND_URL")

STATIC_URL = "/static/"
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]  # Développement
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")  # Production
MEDIA_URL = "/media/"  # Si le logo est uploadé via admin
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

LOCAL_DEV_ORIGINS = [
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://192.168.101.120",
    "http://192.168.101.120:3000",
    "http://192.168.101.120:5173",
    "http://192.168.101.120:5174",
    "http://192.168.101.122",
    "http://192.168.101.122:3000",
    "http://192.168.101.122:5173",
    "http://192.168.101.122:5174",
]

CORS_ALLOWED_ORIGINS = [
    origin.strip() for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if origin.strip()
]
if DEBUG and not CORS_ALLOWED_ORIGINS:
    CORS_ALLOWED_ORIGINS = LOCAL_DEV_ORIGINS.copy()
if DEBUG:
    for origin in LOCAL_DEV_ORIGINS:
        if origin not in CORS_ALLOWED_ORIGINS:
            CORS_ALLOWED_ORIGINS.append(origin)

CORS_ALLOW_CREDENTIALS = True
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
if DEBUG and not CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS = LOCAL_DEV_ORIGINS.copy()
if DEBUG:
    for origin in LOCAL_DEV_ORIGINS:
        if origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(origin)

# Derrière Cloudflare Tunnel / reverse proxy HTTPS
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if not DEBUG:
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:{REDIS_PORT}/1",  # différent du Celery broker
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", f"redis://{REDIS_HOST}:{REDIS_PORT}/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", f"redis://{REDIS_HOST}:{REDIS_PORT}/0")

# --- Microservices IA (ai_gateway) ---
from ai_gateway.conf import (  # noqa: E402
    AI_GATEWAY_ENABLED,
    AI_HTTP_RETRIES,
    AI_HTTP_RETRY_BACKOFF,
    AI_HTTP_TIMEOUT,
    AI_USE_MICROSERVICES,
    NLP_SERVICE_URL,
    PREDICTION_GRID_TIMEOUT,
    PREDICTION_SERVICE_URL,
    PREDICTION_TRAIN_TIMEOUT,
    SCRAPING_HTTP_TIMEOUT,
    SCRAPING_SERVICE_URL,
    VISION_HTTP_TIMEOUT,
    VISION_SERVICE_URL,
)

# Ingestion automatique actualités → signalements source=S
NEWS_INGEST_ENABLED = os.getenv("NEWS_INGEST_ENABLED", "1") == "1"

# Celery est optionnel selon l'environnement (dev local / prod).
try:
    from celery.schedules import crontab

    CELERY_BEAT_SCHEDULE = {
        "refresh_scrapping_cache_every30min": {
            "task": "scrapping.tasks.refresh_scrapping_cache",
            "schedule": crontab(minute="*/30"),
        },
        "ingest_security_news_hourly": {
            "task": "scrapping.tasks.ingest_security_news",
            "schedule": crontab(minute="15"),  # chaque heure à :15
        },
        "export_reports_csv_hourly": {
            "task": "prediction.tasks.export_reports_to_csv",
            "schedule": crontab(minute="5"),  # chaque heure à :05
        },
        "train_prediction_model_hourly": {
            "task": "prediction.tasks.train_prediction_model",
            "schedule": crontab(minute="10"),  # chaque heure à :10
        },
        "train_vision_model_weekly": {
            "task": "reports.tasks.train_vision_model_weekly",
            "schedule": crontab(hour=3, minute=0, day_of_week="sun"),
        },
        "send_weekly_security_reports": {
            "task": "company.tasks.send_weekly_security_reports",
            "schedule": crontab(hour=7, minute=0, day_of_week="mon"),
        },
    }

    CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
except ModuleNotFoundError:
    CELERY_BEAT_SCHEDULE = {}


AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]
