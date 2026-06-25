"""Nested (one-level) menus — tree resolution + sibling-scoped ordering (F9)."""

import pytest

from apps.menus import services
from apps.menus.models import Menu, MenuItem

pytestmark = pytest.mark.django_db


def _menu():
    return Menu.objects.create(name="Primary", slug="primary")


def test_get_menu_items_nests_children_under_parent():
    menu = _menu()
    parent = MenuItem.objects.create(menu=menu, url="/products/", label="Products", position=0)
    MenuItem.objects.create(menu=menu, url="/products/b/", label="Beta", parent=parent, position=1)
    MenuItem.objects.create(menu=menu, url="/products/a/", label="Alpha", parent=parent, position=0)
    MenuItem.objects.create(menu=menu, url="/about/", label="About", position=1)

    items = services.get_menu_items("primary")

    # Top level keeps only roots, in position order.
    assert [i["label"] for i in items] == ["Products", "About"]
    # Children are nested under their parent, in their own position order.
    assert [c["label"] for c in items[0]["children"]] == ["Alpha", "Beta"]
    assert items[0]["children"][0]["url"] == "/products/a/"
    # Leaf nodes still expose an (empty) children list for uniform templates.
    assert items[1]["children"] == []


def test_children_are_excluded_from_top_level():
    menu = _menu()
    parent = MenuItem.objects.create(menu=menu, url="/p/", label="Parent", position=0)
    MenuItem.objects.create(menu=menu, url="/c/", label="Child", parent=parent, position=0)

    items = services.get_menu_items("primary")
    assert len(items) == 1
    assert items[0]["label"] == "Parent"


def test_new_item_position_is_scoped_to_its_sibling_group():
    """Appending a child starts its own 0-based position, independent of roots."""
    menu = _menu()
    parent = MenuItem.objects.create(menu=menu, url="/p/", label="Parent", position=0)
    MenuItem.objects.create(menu=menu, url="/r2/", label="Root2", position=1)

    from apps.menus.repositories import MenuItemRepository

    # First child of `parent` gets position 0 (not 2, the next root position).
    assert MenuItemRepository.next_position(menu, parent=parent) == 0
    # Next root gets position 2 (after the two existing roots).
    assert MenuItemRepository.next_position(menu, parent=None) == 2


def test_move_only_reorders_within_the_same_parent():
    menu = _menu()
    parent = MenuItem.objects.create(menu=menu, url="/p/", label="Parent", position=0)
    root2 = MenuItem.objects.create(menu=menu, url="/r2/", label="Root2", position=1)
    c1 = MenuItem.objects.create(menu=menu, url="/c1/", label="C1", parent=parent, position=0)
    c2 = MenuItem.objects.create(menu=menu, url="/c2/", label="C2", parent=parent, position=1)

    from apps.dashboard import services as dash

    dash.move_menu_item(menu, c1.pk, "down")

    c1.refresh_from_db()
    c2.refresh_from_db()
    root2.refresh_from_db()
    # C1 and C2 swapped; the root item is untouched.
    assert c1.position == 1
    assert c2.position == 0
    assert root2.position == 1
