try:
    from .celery import app as celery_app

    __all__ = ("celery_app",)
except ModuleNotFoundError:
    # Permettre d'exécuter Django (migrations, commandes, etc.) même si Celery
    # n'est pas installé dans l'environnement courant.
    __all__ = tuple()