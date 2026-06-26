"""Per-locale menu-item labels (parler) — resolution + fallback chain (F9)."""

import pytest
from django.utils import translation

from apps.menus import services
from apps.menus.models import LinkType, Menu, MenuItem

pytestmark = pytest.mark.django_db


def test_label_is_resolved_per_active_language():
    menu = Menu.objects.create(name="Primary", slug="primary")
    item = MenuItem.objects.create(menu=menu, link_type=LinkType.CUSTOM, url="/about/")
    item.set_current_language("en")
    item.label = "About"
    item.set_current_language("de")
    item.label = "Über uns"
    item.save()

    with translation.override("en"):
        assert services.get_menu_items("primary")[0]["label"] == "About"
    with translation.override("de"):
        assert services.get_menu_items("primary")[0]["label"] == "Über uns"


def test_missing_translation_falls_back_to_any_label():
    """A locale with no own label shows an existing translation, not an empty string."""
    menu = Menu.objects.create(name="Primary", slug="primary")
    item = MenuItem.objects.create(menu=menu, link_type=LinkType.CUSTOM, url="/x/")
    item.set_current_language("en")
    item.label = "Only English"
    item.save()

    with translation.override("de"):
        assert item.get_label() == "Only English"


def test_blank_label_still_falls_back_to_linked_title():
    from apps.content.models import Page, Status

    menu = Menu.objects.create(name="Primary", slug="primary")
    page = Page.objects.create(title="Pricing", status=Status.PUBLISHED)
    item = MenuItem.objects.create(menu=menu, link_type=LinkType.PAGE, page=page)

    assert item.get_label() == "Pricing"  # no per-locale label set anywhere
