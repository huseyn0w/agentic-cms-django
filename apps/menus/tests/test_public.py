"""Public menu rendering in the shared site shell (F9)."""

import pytest

from apps.menus.models import LinkType, Menu, MenuItem

pytestmark = pytest.mark.django_db


def test_primary_menu_renders_in_header(client):
    menu = Menu.objects.create(name="Primary", slug="primary")
    MenuItem.objects.create(menu=menu, label="Docs", link_type=LinkType.CUSTOM, url="/docs/")
    response = client.get("/")
    assert response.status_code == 200
    assert b"Docs" in response.content
    assert b'href="/docs/"' in response.content


def test_header_falls_back_to_defaults_without_menu(client):
    response = client.get("/")
    assert response.status_code == 200
    # Built-in links remain when no managed menu exists.
    assert b"Services" in response.content
    assert b"Blog" in response.content


def test_footer_menu_renders(client):
    menu = Menu.objects.create(name="Footer", slug="footer")
    MenuItem.objects.create(menu=menu, label="Privacy", link_type=LinkType.CUSTOM, url="/privacy/")
    response = client.get("/")
    assert response.status_code == 200
    assert b"Privacy" in response.content


def test_nested_children_render_in_header_dropdown(client):
    menu = Menu.objects.create(name="Primary", slug="primary")
    parent = MenuItem.objects.create(
        menu=menu, label="Products", link_type=LinkType.CUSTOM, url="/products/"
    )
    MenuItem.objects.create(
        menu=menu, label="Alpha", link_type=LinkType.CUSTOM, url="/products/a/", parent=parent
    )
    html = client.get("/").content.decode()
    # The parent advertises a submenu and the child link is present + reachable.
    assert 'aria-haspopup="true"' in html
    assert 'role="menu"' in html
    assert 'href="/products/a/"' in html
    assert "Alpha" in html


def test_deeply_nested_grandchild_renders_in_header(client):
    """A 2nd-level (grandchild) link is reachable in the recursive header dropdown."""
    menu = Menu.objects.create(name="Primary", slug="primary")
    products = MenuItem.objects.create(
        menu=menu, label="Products", link_type=LinkType.CUSTOM, url="/products/"
    )
    alpha = MenuItem.objects.create(
        menu=menu, label="Alpha", link_type=LinkType.CUSTOM, url="/products/a/", parent=products
    )
    MenuItem.objects.create(
        menu=menu, label="Alpha v2", link_type=LinkType.CUSTOM, url="/products/a/v2/", parent=alpha
    )
    html = client.get("/").content.decode()
    assert 'href="/products/a/v2/"' in html
    assert "Alpha v2" in html


def test_footer_flattens_nested_children(client):
    menu = Menu.objects.create(name="Footer", slug="footer")
    parent = MenuItem.objects.create(
        menu=menu, label="Legal", link_type=LinkType.CUSTOM, url="/legal/"
    )
    MenuItem.objects.create(
        menu=menu, label="Privacy", link_type=LinkType.CUSTOM, url="/privacy/", parent=parent
    )
    html = client.get("/").content.decode()
    assert 'href="/legal/"' in html
    assert 'href="/privacy/"' in html  # child reachable inline in the footer
