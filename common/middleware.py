"""Définit la langue de la requête pour les messages système."""

from common.i18n import get_lang_from_request, set_current_lang


class LanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_current_lang(get_lang_from_request(request))
        return self.get_response(request)
