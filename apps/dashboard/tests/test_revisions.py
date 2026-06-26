"""Dashboard revision history: list, diff, and restore (F7)."""

import pytest
from django.urls import reverse

from apps.content.models import Page, Post

pytestmark = pytest.mark.django_db


def _edit(post, title, body):
    post.title = title
    post.body = body
    post.save()


# --------------------------------------------------------------------------- #
# Posts
# --------------------------------------------------------------------------- #
def test_revision_list_shows_history(client, make_user):
    editor = make_user("ed", role="Editor")
    post = Post.objects.create(title="V1", body="<p>one</p>", author=editor)
    _edit(post, "V2", "<p>two</p>")
    assert post.revisions.count() == 2

    client.force_login(editor)
    response = client.get(reverse("dashboard:post_revisions", args=[post.pk]))
    assert response.status_code == 200
    # Both snapshots are listed.
    assert response.content.count(b"Restore") >= 2


def test_revision_diff_is_shown_when_selected(client, make_user):
    editor = make_user("ed", role="Editor")
    # Bodies share a line so the diff exercises equal + changed rows.
    post = Post.objects.create(title="V1", body="<p>one</p>\n<p>shared</p>", author=editor)
    _edit(post, "V2", "<p>two</p>\n<p>shared</p>")
    first = post.revisions.order_by("created_at").first()

    client.force_login(editor)
    url = reverse("dashboard:post_revisions", args=[post.pk]) + f"?revision={first.pk}"
    response = client.get(url)
    assert response.status_code == 200
    assert b"diff" in response.content.lower()
    assert b"shared" in response.content


def test_restore_reverts_content_and_keeps_history(client, make_user):
    editor = make_user("ed", role="Editor")
    post = Post.objects.create(title="V1", body="<p>one</p>", author=editor)
    _edit(post, "V2", "<p>two</p>")
    first = post.revisions.order_by("created_at").first()

    client.force_login(editor)
    response = client.post(reverse("dashboard:post_revision_restore", args=[post.pk, first.pk]))
    assert response.status_code == 302

    fresh = Post.objects.get(pk=post.pk)
    assert fresh.safe_translation_getter("title") == "V1"
    assert "one" in fresh.safe_translation_getter("body")
    # Restore preserves history and snapshots the restored state.
    assert fresh.revisions.count() == 3


def test_contributor_cannot_restore_others_revision(client, make_user):
    author = make_user("a", role="Author")
    contributor = make_user("c", role="Contributor")
    post = Post.objects.create(title="V1", body="<p>one</p>", author=author)
    _edit(post, "V2", "<p>two</p>")
    rev = post.revisions.first()

    client.force_login(contributor)
    response = client.post(reverse("dashboard:post_revision_restore", args=[post.pk, rev.pk]))
    assert response.status_code == 404


def test_revisions_view_scoped_to_own_posts(client, make_user):
    author = make_user("a", role="Author")
    other = make_user("b", role="Author")
    post = Post.objects.create(title="V1", body="<p>x</p>", author=other)

    client.force_login(author)
    response = client.get(reverse("dashboard:post_revisions", args=[post.pk]))
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
def test_page_revision_list_and_diff(client, make_user):
    editor = make_user("ed", role="Editor")
    page = Page.objects.create(title="P1", body="<p>alpha</p>", author=editor)
    page.title = "P2"
    page.body = "<p>beta</p>"
    page.save()
    first = page.revisions.order_by("created_at").first()

    client.force_login(editor)
    response = client.get(reverse("dashboard:page_revisions", args=[page.pk]))
    assert response.status_code == 200
    assert response.content.count(b"Restore") >= 2

    diff = client.get(reverse("dashboard:page_revisions", args=[page.pk]) + f"?revision={first.pk}")
    assert diff.status_code == 200
    assert b"diff" in diff.content.lower()


def test_page_revision_restore(client, make_user):
    editor = make_user("ed", role="Editor")
    page = Page.objects.create(title="P1", body="<p>alpha</p>", author=editor)
    page.title = "P2"
    page.body = "<p>beta</p>"
    page.save()
    first = page.revisions.order_by("created_at").first()

    client.force_login(editor)
    response = client.post(reverse("dashboard:page_revision_restore", args=[page.pk, first.pk]))
    assert response.status_code == 302
    fresh = Page.objects.get(pk=page.pk)
    assert fresh.safe_translation_getter("title") == "P1"
