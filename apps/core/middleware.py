"""Core middleware."""

from django.conf import settings
from django.utils import translation

# Admin surfaces served OUTSIDE i18n_patterns (stable, prefix-free URLs). With
# prefix_default_language=False, Django's LocaleMiddleware forces the default
# LANGUAGE_CODE on any URL that carries no language prefix — which is every admin
# URL — so an operator's interface-language choice would otherwise be ignored on
# the dashboard. AdminLocaleMiddleware re-applies that choice from the standard
# django_language cookie (written by the set_language view) for these prefixes
# only; public unprefixed URLs (e.g. /blog/) are deliberately left on the default
# language, which is the whole point of prefix_default_language=False.
ADMIN_LOCALE_PREFIXES = ("/dashboard/", "/library/")


class AdminLocaleMiddleware:
    """Activate the cookie-selected UI language on the (non-i18n) admin surfaces.

    Must sit immediately AFTER django.middleware.locale.LocaleMiddleware so it can
    override the default language that LocaleMiddleware pins for prefix-free URLs.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._supported = dict(settings.LANGUAGES)

    def __call__(self, request):
        if request.path_info.startswith(ADMIN_LOCALE_PREFIXES):
            lang = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
            if lang and lang in self._supported and translation.check_for_language(lang):
                translation.activate(lang)
                request.LANGUAGE_CODE = translation.get_language()
        return self.get_response(request)
