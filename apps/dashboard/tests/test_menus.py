"""Dashboard menu builder: CRUD + reorder (F9)."""

import json

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
    # `label` is now a parler translated field, so read it via get_label().
    positions = [(i.get_label(), i.position) for i in menu.items.order_by("position")]
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
    child = menu.items.get(url="/a/")
    assert child.get_label() == "Alpha"
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


def test_item_with_children_can_be_nested_under_a_sibling(client, make_user):
    """Arbitrary depth: an item that has children may itself be nested under a
    sibling that is NOT one of its descendants (the subtree moves with it)."""
    client.force_login(make_user("boss", role="Administrator"))
    menu = Menu.objects.create(name="Primary", slug="primary")
    parent = MenuItem.objects.create(menu=menu, label="Parent", url="/p/")
    root2 = MenuItem.objects.create(menu=menu, label="Root2", url="/r/")
    MenuItem.objects.create(menu=menu, label="Child", url="/c/", parent=parent)
    response = client.post(
        reverse("dashboard:menu_item_edit", args=[menu.pk, parent.pk]),
        {"parent": root2.pk, "label": "Parent", "link_type": LinkType.CUSTOM, "url": "/p/"},
    )
    assert response.status_code == 302  # accepted
    parent.refresh_from_db()
    assert parent.parent_id == root2.pk


def test_item_cannot_be_nested_under_its_own_descendant(client, make_user):
    """Cycle prevention: selecting a descendant as parent is rejected."""
    client.force_login(make_user("boss", role="Administrator"))
    menu = Menu.objects.create(name="Primary", slug="primary")
    parent = MenuItem.objects.create(menu=menu, label="Parent", url="/p/")
    child = MenuItem.objects.create(menu=menu, label="Child", url="/c/", parent=parent)
    grandchild = MenuItem.objects.create(menu=menu, label="Grand", url="/g/", parent=child)
    response = client.post(
        reverse("dashboard:menu_item_edit", args=[menu.pk, parent.pk]),
        {"parent": grandchild.pk, "label": "Parent", "link_type": LinkType.CUSTOM, "url": "/p/"},
    )
    assert response.status_code == 200  # rejected, re-rendered
    parent.refresh_from_db()
    assert parent.parent_id is None


def test_parent_choices_exclude_self_and_descendants(client, make_user):
    """The parent <select> hides the item itself and every item beneath it."""
    client.force_login(make_user("boss", role="Administrator"))
    menu = Menu.objects.create(name="Primary", slug="primary")
    parent = MenuItem.objects.create(menu=menu, label="Parent", url="/p/")
    child = MenuItem.objects.create(menu=menu, label="ChildOfP", url="/c/", parent=parent)
    MenuItem.objects.create(menu=menu, label="GrandOfP", url="/g/", parent=child)
    other = MenuItem.objects.create(menu=menu, label="OtherRoot", url="/o/")
    html = client.get(
        reverse("dashboard:menu_item_edit", args=[menu.pk, parent.pk])
    ).content.decode()
    # Self + descendants are not offered as a parent (would create a cycle)…
    assert f'value="{parent.pk}"' not in html
    assert f'value="{child.pk}"' not in html
    # …but a non-descendant sibling is a valid parent.
    assert f'value="{other.pk}"' in html


def test_reorder_endpoint_persists_sibling_order(client, make_user):
    """Posting a new order of sibling ids persists their position (drag-drop save)."""
    client.force_login(make_user("boss", role="Administrator"))
    menu = Menu.objects.create(name="Primary", slug="primary")
    a = MenuItem.objects.create(menu=menu, label="A", url="/a/", position=0)
    b = MenuItem.objects.create(menu=menu, label="B", url="/b/", position=1)
    c = MenuItem.objects.create(menu=menu, label="C", url="/c/", position=2)
    response = client.post(
        reverse("dashboard:menu_item_reorder", args=[menu.pk]),
        data=json.dumps({"order": [c.pk, a.pk, b.pk]}),
        content_type="application/json",
    )
    assert response.status_code == 200
    a.refresh_from_db()
    b.refresh_from_db()
    c.refresh_from_db()
    assert (c.position, a.position, b.position) == (0, 1, 2)


def test_reorder_endpoint_is_scoped_to_the_menu(client, make_user):
    """Ids from another menu are ignored — only this menu's items are renumbered."""
    client.force_login(make_user("boss", role="Administrator"))
    menu = Menu.objects.create(name="Primary", slug="primary")
    other = Menu.objects.create(name="Footer", slug="footer")
    a = MenuItem.objects.create(menu=menu, label="A", url="/a/", position=0)
    b = MenuItem.objects.create(menu=menu, label="B", url="/b/", position=1)
    foreign = MenuItem.objects.create(menu=other, label="X", url="/x/", position=5)
    response = client.post(
        reverse("dashboard:menu_item_reorder", args=[menu.pk]),
        data=json.dumps({"order": [b.pk, foreign.pk, a.pk]}),
        content_type="application/json",
    )
    assert response.status_code == 200
    a.refresh_from_db()
    b.refresh_from_db()
    foreign.refresh_from_db()
    assert (b.position, a.position) == (0, 1)
    assert foreign.position == 5  # untouched


def test_reorder_endpoint_rejects_unauthorized(client, make_user):
    client.force_login(make_user("ed", role="Editor"))
    menu = Menu.objects.create(name="Primary", slug="primary")
    response = client.post(
        reverse("dashboard:menu_item_reorder", args=[menu.pk]),
        data=json.dumps({"order": []}),
        content_type="application/json",
    )
    assert response.status_code == 403


def test_manage_view_indents_child_items(client, make_user):
    client.force_login(make_user("boss", role="Administrator"))
    menu = Menu.objects.create(name="Primary", slug="primary")
    parent = MenuItem.objects.create(menu=menu, label="Products", url="/p/")
    MenuItem.objects.create(menu=menu, label="Alpha", url="/a/", parent=parent)
    html = client.get(reverse("dashboard:menu_manage", args=[menu.pk])).content.decode()
    assert "Products" in html
    assert "Alpha" in html
    assert "↳" in html  # nested-item marker


def test_item_label_is_edited_per_language(client, make_user):
    """The ?language= tab edits only that locale's label (parler), not the others."""
    client.force_login(make_user("boss", role="Administrator"))
    menu = Menu.objects.create(name="Primary", slug="primary")
    item = MenuItem.objects.create(menu=menu, url="/about/")
    item.set_current_language("en")
    item.label = "About"
    item.save()

    edit_url = reverse("dashboard:menu_item_edit", args=[menu.pk, item.pk])
    client.post(
        f"{edit_url}?language=de",
        {"label": "Über uns", "link_type": LinkType.CUSTOM, "url": "/about/"},
    )

    item.refresh_from_db()
    assert item.safe_translation_getter("label", language_code="en") == "About"
    assert item.safe_translation_getter("label", language_code="de") == "Über uns"
