"""Dashboard trash / restore / permanent-delete flows (F6)."""

import pytest
from django.urls import reverse

from apps.content.models import Page, Post

pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------------- #
# Posts
# --------------------------------------------------------------------------- #
def test_delete_now_trashes_instead_of_destroying(client, make_user):
    editor = make_user("ed", role="Editor")
    post = Post.objects.create(title="Doomed", author=editor)
    client.force_login(editor)
    response = client.post(reverse("dashboard:post_delete", args=[post.pk]))
    assert response.status_code == 302
    # Row still exists, just soft-deleted.
    assert Post.objects.with_trashed().filter(pk=post.pk).exists()
    assert Post.objects.only_trashed().filter(pk=post.pk).exists()


def test_trash_list_shows_only_trashed_posts(client, make_user):
    editor = make_user("ed", role="Editor")
    Post.objects.create(title="Live one", author=editor)
    gone = Post.objects.create(title="Gone one", author=editor)
    gone.trash()
    client.force_login(editor)
    response = client.get(reverse("dashboard:post_trash"))
    assert response.status_code == 200
    assert b"Gone one" in response.content
    assert b"Live one" not in response.content


def test_restore_brings_post_back_to_list(client, make_user):
    editor = make_user("ed", role="Editor")
    post = Post.objects.create(title="Comeback", author=editor)
    post.trash()
    client.force_login(editor)
    response = client.post(reverse("dashboard:post_restore", args=[post.pk]))
    assert response.status_code == 302
    assert Post.objects.filter(pk=post.pk).exists()


def test_permanent_delete_destroys_the_row(client, make_user):
    editor = make_user("ed", role="Editor")
    post = Post.objects.create(title="Forever gone", author=editor)
    post.trash()
    client.force_login(editor)
    response = client.post(reverse("dashboard:post_destroy", args=[post.pk]))
    assert response.status_code == 302
    assert not Post.objects.with_trashed().filter(pk=post.pk).exists()


def test_author_cannot_restore(client, make_user):
    # Trash is gated on delete_post (Editors/Admins only), so Authors are blocked.
    a = make_user("a", role="Author")
    b = make_user("b", role="Author")
    other = Post.objects.create(title="Bs post", author=b)
    other.trash()
    client.force_login(a)
    response = client.post(reverse("dashboard:post_restore", args=[other.pk]))
    assert response.status_code == 403
    assert Post.objects.only_trashed().filter(pk=other.pk).exists()


def test_contributor_cannot_trash(client, make_user):
    contributor = make_user("c", role="Contributor")
    post = Post.objects.create(title="Mine", author=contributor)
    client.force_login(contributor)
    assert client.post(reverse("dashboard:post_delete", args=[post.pk])).status_code == 403
    assert Post.objects.filter(pk=post.pk).exists()


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
def test_page_delete_trashes_and_restore_works(client, make_user):
    editor = make_user("ed", role="Editor")
    page = Page.objects.create(title="About", author=editor)
    client.force_login(editor)
    client.post(reverse("dashboard:page_delete", args=[page.pk]))
    assert Page.objects.only_trashed().filter(pk=page.pk).exists()

    trash = client.get(reverse("dashboard:page_trash"))
    assert b"About" in trash.content

    client.post(reverse("dashboard:page_restore", args=[page.pk]))
    assert Page.objects.filter(pk=page.pk).exists()


def test_page_permanent_delete(client, make_user):
    editor = make_user("ed", role="Editor")
    page = Page.objects.create(title="Trashme", author=editor)
    page.trash()
    client.force_login(editor)
    client.post(reverse("dashboard:page_destroy", args=[page.pk]))
    assert not Page.objects.with_trashed().filter(pk=page.pk).exists()
