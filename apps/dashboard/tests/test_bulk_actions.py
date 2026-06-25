"""Bulk table actions + the U5 admin UI components (confirm dialog, toasts)."""

import pytest
from django.urls import reverse

from apps.content.models import Post, Status

pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------------- #
# Bulk trash (view -> service -> repository)
# --------------------------------------------------------------------------- #
def test_bulk_trash_moves_selected_posts(client, make_user):
    editor = make_user("ed", role="Editor")
    a = Post.objects.create(title="One", author=editor)
    b = Post.objects.create(title="Two", author=editor)
    keep = Post.objects.create(title="Three", author=editor)
    client.force_login(editor)

    response = client.post(
        reverse("dashboard:post_bulk_action"),
        {"action": "trash", "ids": [a.pk, b.pk]},
    )
    assert response.status_code == 302
    assert Post.objects.only_trashed().filter(pk__in=[a.pk, b.pk]).count() == 2
    assert Post.objects.filter(pk=keep.pk).exists()  # untouched, still live


def test_editor_can_bulk_trash_any_authors_posts(client, make_user):
    """Editors are content managers, so the bulk action covers any author's posts."""
    editor = make_user("ed", role="Editor")
    author = make_user("au", role="Author")
    theirs = Post.objects.create(title="Theirs", author=author)
    client.force_login(editor)

    client.post(
        reverse("dashboard:post_bulk_action"),
        {"action": "trash", "ids": [theirs.pk]},
    )
    assert Post.objects.only_trashed().filter(pk=theirs.pk).exists()


def test_bulk_action_requires_delete_permission(client, make_user):
    contributor = make_user("con", role="Contributor")
    post = Post.objects.create(title="Safe", author=contributor)
    client.force_login(contributor)
    response = client.post(
        reverse("dashboard:post_bulk_action"),
        {"action": "trash", "ids": [post.pk]},
    )
    assert response.status_code == 403
    assert Post.objects.filter(pk=post.pk).exists()


def test_unknown_bulk_action_is_a_noop(client, make_user):
    editor = make_user("ed", role="Editor")
    post = Post.objects.create(title="Keep", author=editor, status=Status.PUBLISHED)
    client.force_login(editor)
    client.post(
        reverse("dashboard:post_bulk_action"),
        {"action": "explode", "ids": [post.pk]},
    )
    assert Post.objects.filter(pk=post.pk).exists()


def test_non_integer_ids_do_not_500(client, make_user):
    """Tampered/garbage ids are dropped, not passed to an int pk lookup."""
    editor = make_user("ed", role="Editor")
    post = Post.objects.create(title="Untouched", author=editor)
    client.force_login(editor)
    response = client.post(
        reverse("dashboard:post_bulk_action"),
        {"action": "trash", "ids": ["abc", "", str(post.pk)]},
    )
    assert response.status_code == 302
    # The valid id still trashed; the garbage ones were ignored (no 500).
    assert Post.objects.only_trashed().filter(pk=post.pk).exists()


# --------------------------------------------------------------------------- #
# U5 component wiring (guard tests)
# --------------------------------------------------------------------------- #
def test_post_list_renders_bulk_select_and_confirm(client, make_user):
    editor = make_user("ed", role="Editor")
    Post.objects.create(title="Listed", author=editor)
    client.force_login(editor)
    html = client.get(reverse("dashboard:post_list")).content.decode()

    assert 'aria-label="Select all posts"' in html
    assert reverse("dashboard:post_bulk_action") in html
    # Destructive forms opt into the accessible dialog, not native confirm().
    assert "data-dp-confirm" in html
    assert 'onsubmit="return confirm' not in html


def test_dashboard_shell_includes_toasts_and_dialog(client, make_user):
    editor = make_user("ed", role="Editor")
    client.force_login(editor)
    html = client.get(reverse("dashboard:post_list")).content.decode()

    # Confirm dialog is a focus-trapped modal.
    assert 'role="dialog"' in html
    assert 'aria-modal="true"' in html
    # Toast live region for Django messages.
    assert 'aria-live="polite"' in html
