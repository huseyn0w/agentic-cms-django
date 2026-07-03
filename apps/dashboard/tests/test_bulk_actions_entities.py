"""Bulk multi-select actions for pages, categories, tags, users, comments (§1).

Mirrors the PostBulkActionView pattern: a POST endpoint per entity taking
``action`` + a list of ``ids``, scoped/validated in the service layer. Action set
per entity matches its capabilities:

- pages       → trash (soft-delete, like posts)
- categories  → delete (hard; no soft-delete)
- tags        → delete (hard; no soft-delete)
- users       → deactivate / activate (reversible; never the acting user)
- comments    → approve / spam / delete
"""

import pytest
from django.urls import reverse

from apps.comments.models import Comment, CommentStatus
from apps.content.models import Category, Page, Post, Status, Tag

pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------------- #
# Pages — bulk trash
# --------------------------------------------------------------------------- #
def test_bulk_trash_pages(client, make_user):
    editor = make_user("ed", role="Editor")
    a = Page.objects.create(title="A", author=editor)
    b = Page.objects.create(title="B", author=editor)
    keep = Page.objects.create(title="Keep", author=editor)
    client.force_login(editor)

    resp = client.post(
        reverse("dashboard:page_bulk_action"), {"action": "trash", "ids": [a.pk, b.pk]}
    )
    assert resp.status_code == 302
    assert Page.objects.only_trashed().filter(pk__in=[a.pk, b.pk]).count() == 2
    assert Page.objects.filter(pk=keep.pk).exists()


def test_page_bulk_requires_delete_permission(client, make_user):
    author = make_user("au", role="Author")  # no delete_page
    page = Page.objects.create(title="Safe", author=author)
    client.force_login(author)
    resp = client.post(reverse("dashboard:page_bulk_action"), {"action": "trash", "ids": [page.pk]})
    assert resp.status_code == 403
    assert Page.objects.filter(pk=page.pk).exists()


# --------------------------------------------------------------------------- #
# Categories — bulk delete (hard)
# --------------------------------------------------------------------------- #
def test_bulk_delete_categories(client, make_user):
    editor = make_user("ed", role="Editor")
    a = Category.objects.create(name="A", slug="a")
    b = Category.objects.create(name="B", slug="b")
    keep = Category.objects.create(name="Keep", slug="keep")
    client.force_login(editor)

    resp = client.post(
        reverse("dashboard:category_bulk_action"),
        {"action": "delete", "ids": [a.pk, b.pk]},
    )
    assert resp.status_code == 302
    assert not Category.objects.filter(pk__in=[a.pk, b.pk]).exists()
    assert Category.objects.filter(pk=keep.pk).exists()


def test_category_bulk_requires_delete_permission(client, make_user):
    author = make_user("au", role="Author")
    cat = Category.objects.create(name="Safe", slug="safe")
    client.force_login(author)
    resp = client.post(
        reverse("dashboard:category_bulk_action"), {"action": "delete", "ids": [cat.pk]}
    )
    assert resp.status_code == 403
    assert Category.objects.filter(pk=cat.pk).exists()


# --------------------------------------------------------------------------- #
# Tags — bulk delete (hard)
# --------------------------------------------------------------------------- #
def test_bulk_delete_tags(client, make_user):
    editor = make_user("ed", role="Editor")
    a = Tag.objects.create(name="A", slug="a")
    b = Tag.objects.create(name="B", slug="b")
    client.force_login(editor)

    resp = client.post(
        reverse("dashboard:tag_bulk_action"), {"action": "delete", "ids": [a.pk, b.pk]}
    )
    assert resp.status_code == 302
    assert not Tag.objects.filter(pk__in=[a.pk, b.pk]).exists()


# --------------------------------------------------------------------------- #
# Users — bulk deactivate / activate (never the acting user)
# --------------------------------------------------------------------------- #
def test_bulk_deactivate_users(client, make_user):
    admin = make_user("boss", role="Administrator")
    u1 = make_user("u1", role="Author")
    u2 = make_user("u2", role="Author")
    client.force_login(admin)

    resp = client.post(
        reverse("dashboard:user_bulk_action"),
        {"action": "deactivate", "ids": [u1.pk, u2.pk]},
    )
    assert resp.status_code == 302
    u1.refresh_from_db()
    u2.refresh_from_db()
    assert not u1.is_active and not u2.is_active


def test_bulk_activate_users(client, make_user):
    admin = make_user("boss", role="Administrator")
    u1 = make_user("u1", role="Author")
    u1.is_active = False
    u1.save()
    client.force_login(admin)

    client.post(reverse("dashboard:user_bulk_action"), {"action": "activate", "ids": [u1.pk]})
    u1.refresh_from_db()
    assert u1.is_active


def test_user_bulk_never_deactivates_the_acting_user(client, make_user):
    """Self-lockout guard: the acting admin can't deactivate themselves in bulk."""
    admin = make_user("boss", role="Administrator")
    client.force_login(admin)
    client.post(
        reverse("dashboard:user_bulk_action"),
        {"action": "deactivate", "ids": [admin.pk]},
    )
    admin.refresh_from_db()
    assert admin.is_active  # still active


def test_user_bulk_requires_manage_users(client, make_user):
    editor = make_user("ed", role="Editor")  # no manage_users
    victim = make_user("v", role="Author")
    client.force_login(editor)
    resp = client.post(
        reverse("dashboard:user_bulk_action"),
        {"action": "deactivate", "ids": [victim.pk]},
    )
    assert resp.status_code == 403
    victim.refresh_from_db()
    assert victim.is_active


# --------------------------------------------------------------------------- #
# Comments — bulk approve / spam / delete
# --------------------------------------------------------------------------- #
@pytest.fixture
def post(make_user):
    author = make_user("writer")
    return Post.objects.create(title="P", author=author, status=Status.PUBLISHED)


def test_bulk_approve_comments(client, make_user, post):
    editor = make_user("ed", role="Editor")
    a = Comment.objects.create(post=post, name="A", body="a")
    b = Comment.objects.create(post=post, name="B", body="b")
    client.force_login(editor)

    resp = client.post(
        reverse("dashboard:comment_bulk_action"),
        {"action": "approve", "ids": [a.pk, b.pk]},
    )
    assert resp.status_code == 302
    a.refresh_from_db()
    b.refresh_from_db()
    assert a.status == CommentStatus.APPROVED and b.status == CommentStatus.APPROVED


def test_bulk_spam_comments(client, make_user, post):
    editor = make_user("ed", role="Editor")
    c = Comment.objects.create(post=post, name="A", body="a")
    client.force_login(editor)
    client.post(reverse("dashboard:comment_bulk_action"), {"action": "spam", "ids": [c.pk]})
    c.refresh_from_db()
    assert c.status == CommentStatus.SPAM


def test_bulk_delete_comments(client, make_user, post):
    editor = make_user("ed", role="Editor")
    c = Comment.objects.create(post=post, name="A", body="a")
    client.force_login(editor)
    client.post(reverse("dashboard:comment_bulk_action"), {"action": "delete", "ids": [c.pk]})
    assert not Comment.objects.filter(pk=c.pk).exists()


def test_comment_bulk_requires_moderate_permission(client, make_user, post):
    author = make_user("au", role="Author")  # no moderate_comment
    c = Comment.objects.create(post=post, name="A", body="a")
    client.force_login(author)
    resp = client.post(
        reverse("dashboard:comment_bulk_action"), {"action": "delete", "ids": [c.pk]}
    )
    assert resp.status_code == 403
    assert Comment.objects.filter(pk=c.pk).exists()


# --------------------------------------------------------------------------- #
# Template wiring (guard tests)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "list_url,bulk_url,select_label",
    [
        ("dashboard:page_list", "dashboard:page_bulk_action", "Select all pages"),
        ("dashboard:category_list", "dashboard:category_bulk_action", "Select all categories"),
        ("dashboard:tag_list", "dashboard:tag_bulk_action", "Select all tags"),
        ("dashboard:user_list", "dashboard:user_bulk_action", "Select all users"),
        ("dashboard:comment_list", "dashboard:comment_bulk_action", "Select all comments"),
    ],
)
def test_list_renders_bulk_bar(client, make_user, list_url, bulk_url, select_label):
    admin = make_user("boss", role="Administrator")
    client.force_login(admin)
    html = client.get(reverse(list_url)).content.decode()
    assert reverse(bulk_url) in html
    assert f'aria-label="{select_label}"' in html
