"""Menu model resolution + public service (F9)."""

import pytest

from apps.content.models import Page, Post, Status
from apps.menus import services
from apps.menus.models import LinkType, Menu, MenuItem

pytestmark = pytest.mark.django_db


def test_custom_item_uses_url_and_label():
    menu = Menu.objects.create(name="Primary", slug="primary")
    item = MenuItem.objects.create(
        menu=menu, link_type=LinkType.CUSTOM, url="/about/", label="About us"
    )
    assert item.get_url() == "/about/"
    assert item.get_label() == "About us"


def test_post_item_falls_back_to_post_title():
    menu = Menu.objects.create(name="Primary", slug="primary")
    post = Post.objects.create(title="Hello world", status=Status.PUBLISHED)
    item = MenuItem.objects.create(menu=menu, link_type=LinkType.POST, post=post)
    assert item.get_url() == post.get_absolute_url()
    assert item.get_label() == "Hello world"


def test_explicit_label_overrides_linked_title():
    menu = Menu.objects.create(name="Primary", slug="primary")
    page = Page.objects.create(title="Untitled", status=Status.PUBLISHED)
    item = MenuItem.objects.create(
        menu=menu, link_type=LinkType.PAGE, page=page, label="Start here"
    )
    assert item.get_label() == "Start here"
    assert item.get_url() == page.get_absolute_url()


def test_get_menu_items_returns_resolved_list_in_order():
    menu = Menu.objects.create(name="Primary", slug="primary")
    MenuItem.objects.create(menu=menu, url="/b/", label="B", position=1)
    MenuItem.objects.create(menu=menu, url="/a/", label="A", position=0)
    items = services.get_menu_items("primary")
    # Flat menus resolve to top-level nodes, each carrying an empty children list.
    assert items == [
        {"label": "A", "url": "/a/", "children": []},
        {"label": "B", "url": "/b/", "children": []},
    ]


def test_get_menu_items_empty_for_unknown_slug():
    assert services.get_menu_items("does-not-exist") == []
