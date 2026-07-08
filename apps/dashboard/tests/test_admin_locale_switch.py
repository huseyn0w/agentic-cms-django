"""The admin UI honours the operator's chosen interface language.

The dashboard lives outside i18n_patterns, and with prefix_default_language=False
Django's LocaleMiddleware pins every prefix-free URL to the default language.
AdminLocaleMiddleware re-applies the language stored in the django_language cookie
(written by the set_language view / the topbar switcher) for the admin surfaces,
while public unprefixed URLs stay on the default language.
"""

import re

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse


def _html_lang(html: str) -> str:
    m = re.search(r'<html lang="([^"]+)"', html)
    return m.group(1) if m else ""


@pytest.fixture
def admin_client(db):
    admin = get_user_model().objects.create_superuser(
        username="locadmin", email="locadmin@example.com", password="pw-12345678"
    )
    c = Client()
    c.force_login(admin)
    return c


def test_dashboard_defaults_to_english(admin_client):
    html = admin_client.get("/dashboard/").content.decode()
    assert _html_lang(html) == "en"
    assert "Posts" in html


@pytest.mark.parametrize(
    "lang,expected",
    [
        ("de", ["Beiträge", "Abmelden", "Einstellungen"]),
        ("ru", ["Посты", "Выйти", "Настройки"]),
    ],
)
def test_switcher_localizes_dashboard(admin_client, lang, expected):
    # The switcher POSTs to set_language, which stores the choice in the cookie.
    admin_client.post(reverse("set_language"), {"language": lang, "next": "/dashboard/"})
    html = admin_client.get("/dashboard/").content.decode()
    assert _html_lang(html) == lang
    for word in expected:
        assert word in html, f"missing {word!r} under {lang}"
    assert f'<option value="{lang}" selected>{lang.upper()}</option>' in html


def test_media_library_is_localized(admin_client):
    admin_client.post(reverse("set_language"), {"language": "de", "next": "/library/"})
    html = admin_client.get("/library/").content.decode()
    assert _html_lang(html) == "de"


def test_public_url_stays_default_language_with_admin_cookie(admin_client):
    # Selecting an admin language must NOT leak into public prefix-free URLs:
    # /blog/ etc. stay on the default language (the point of prefix_default_language=False).
    admin_client.post(reverse("set_language"), {"language": "de", "next": "/dashboard/"})
    html = admin_client.get("/").content.decode()
    assert _html_lang(html) == "en"
