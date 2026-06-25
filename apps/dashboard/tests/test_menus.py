"""Dashboard menu builder: CRUD + reorder (F9)."""

import pytest
from django.urls import reverse

from apps.menus.models import LinkType, Menu, MenuItem

pytestmark = pytest.mark.django_db


def test_admin_creates_menu_and_is_sent_to_builder(client, make_user):
    client.force_login(make_user("boss", role="Administrator"))
    response = client.post(reverse("dashboard:menu_create"), {"name": "Primary", "slug": "primary"})
    menu = Menu.objects.get()
    assert response.status_code == 302
    assert response.url == reverse("dashboard:menu_manage", args=[menu.pk])


def test_add_items_get_appended_positions(client, make_user):
    client.force_login(make_user("boss", role="Administrator"))
    menu = Menu.objects.create(name="Primary", slug="primary")
    url = reverse("dashboard:menu_item_create", args=[menu.pk])
    client.post(url, {"label": "First", "link_type": LinkType.CUSTOM, "url": "/a/"})
    client.post(url, {"label": "Second", "link_type": LinkType.CUSTOM, "url": "/b/"})
    positions = list(menu.items.values_list("label", "position").order_by("position"))
    assert positions == [("First", 0), ("Second", 1)]


def test_custom_item_without_url_is_rejected(client, make_user):
    client.force_login(make_user("boss", role="Administrator"))
    menu = Menu.objects.create(name="Primary", slug="primary")
    response = client.post(
        reverse("dashboard:menu_item_create", args=[menu.pk]),
        {"label": "Bad", "link_type": LinkType.CUSTOM, "url": ""},
    )
    assert response.status_code == 200  # re-rendered with errors
    assert menu.items.count() == 0


def test_move_item_up_swaps_order(client, make_user):
    client.force_login(make_user("boss", role="Administrator"))
    menu = Menu.objects.create(name="Primary", slug="primary")
    a = MenuItem.objects.create(menu=menu, label="A", url="/a/", position=0)
    b = MenuItem.objects.create(menu=menu, label="B", url="/b/", position=1)
    client.post(reverse("dashboard:menu_item_move", args=[menu.pk, b.pk, "up"]))
    a.refresh_from_db()
    b.refresh_from_db()
    assert b.position < a.position


def test_delete_item_and_menu(client, make_user):
    client.force_login(make_user("boss", role="Administrator"))
    menu = Menu.objects.create(name="Primary", slug="primary")
    item = MenuItem.objects.create(menu=menu, label="A", url="/a/")
    client.post(reverse("dashboard:menu_item_delete", args=[menu.pk, item.pk]))
    assert menu.items.count() == 0
    client.post(reverse("dashboard:menu_delete", args=[menu.pk]))
    assert not Menu.objects.filter(pk=menu.pk).exists()


def test_manage_view_lists_items_with_reorder_controls(client, make_user):
    client.force_login(make_user("boss", role="Administrator"))
    menu = Menu.objects.create(name="Primary", slug="primary")
    MenuItem.objects.create(menu=menu, label="Home", url="/")
    response = client.get(reverse("dashboard:menu_manage", args=[menu.pk]))
    assert response.status_code == 200
    assert b"Home" in response.content
    assert b"Move up" in response.content


def test_edit_item_updates_label(client, make_user):
    client.force_login(make_user("boss", role="Administrator"))
    menu = Menu.objects.create(name="Primary", slug="primary")
    item = MenuItem.objects.create(menu=menu, label="Old", url="/x/")
    assert (
        client.get(reverse("dashboard:menu_item_edit", args=[menu.pk, item.pk])).status_code == 200
    )
    client.post(
        reverse("dashboard:menu_item_edit", args=[menu.pk, item.pk]),
        {"label": "New", "link_type": LinkType.CUSTOM, "url": "/x/"},
    )
    item.refresh_from_db()
    assert item.label == "New"


def test_editor_without_manage_settings_is_blocked(client, make_user):
    client.force_login(make_user("ed", role="Editor"))
    assert client.get(reverse("dashboard:menu_list")).status_code == 403


# --------------------------------------------------------------------------- #
# Nesting (F9 — one level deep)
# --------------------------------------------------------------------------- #
def test_item_can_be_created_under_a_parent(client, make_user):
    client.force_login(make_user("boss", role="Administrator"))
    menu = Menu.objects.create(name="Primary", slug="primary")
    parent = MenuItem.objects.create(menu=menu, label="Products", url="/p/")
    client.post(
        reverse("dashboard:menu_item_create", args=[menu.pk]),
        {"parent": parent.pk, "label": "Alpha", "link_type": LinkType.CUSTOM, "url": "/a/"},
    )
    child = menu.items.get(label="Alpha")
    assert child.parent_id == parent.pk
    assert child.position == 0  # own sibling group, not appended after the parent


def test_parent_choices_exclude_self_and_other_menus(client, make_user):
    client.force_login(make_user("boss", role="Administrator"))
    menu = Menu.objects.create(name="Primary", slug="primary")
    other = Menu.objects.create(name="Footer", slug="footer")
    here = MenuItem.objects.create(menu=menu, label="Here", url="/h/")
    MenuItem.objects.create(menu=other, label="Elsewhere", url="/e/")
    html = client.get(reverse("dashboard:menu_item_edit", args=[menu.pk, here.pk])).content.decode()
    # The parent <select> offers neither the item itself nor another menu's items.
    assert "Elsewhere" not in html
    assert f'value="{here.pk}"' not in html


def test_item_with_children_cannot_be_nested(client, make_user):
    client.force_login(make_user("boss", role="Administrator"))
    menu = Menu.objects.create(name="Primary", slug="primary")
    parent = MenuItem.objects.create(menu=menu, label="Parent", url="/p/")
    root2 = MenuItem.objects.create(menu=menu, label="Root2", url="/r/")
    MenuItem.objects.create(menu=menu, label="Child", url="/c/", parent=parent)
    response = client.post(
        reverse("dashboard:menu_item_edit", args=[menu.pk, parent.pk]),
        {"parent": root2.pk, "label": "Parent", "link_type": LinkType.CUSTOM, "url": "/p/"},
    )
    assert response.status_code == 200  # rejected, re-rendered
    parent.refresh_from_db()
    assert parent.parent_id is None


def test_manage_view_indents_child_items(client, make_user):
    client.force_login(make_user("boss", role="Administrator"))
    menu = Menu.objects.create(name="Primary", slug="primary")
    parent = MenuItem.objects.create(menu=menu, label="Products", url="/p/")
    MenuItem.objects.create(menu=menu, label="Alpha", url="/a/", parent=parent)
    html = client.get(reverse("dashboard:menu_manage", args=[menu.pk])).content.decode()
    assert "Products" in html
    assert "Alpha" in html
    assert "↳" in html  # nested-item marker
