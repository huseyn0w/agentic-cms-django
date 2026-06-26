"""Soft-delete / trash / restore behaviour for posts and pages (F6).

The default manager hides soft-deleted rows, so every existing public/admin/
search/sitemap query excludes them automatically; trash views opt back in via
``with_trashed()`` / ``only_trashed()``.
"""

import pytest
from django.contrib.auth import get_user_model

from apps.content.models import Page, Post, Status

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def author():
    return User.objects.create_user(username="alice", email="a@example.com")


# --------------------------------------------------------------------------- #
# Model state + manager scoping
# --------------------------------------------------------------------------- #
def test_new_post_is_not_trashed(author):
    post = Post.objects.create(title="Live", author=author)
    assert post.is_trashed is False
    assert post.deleted_at is None


def test_trashed_post_hidden_from_default_manager(author):
    post = Post.objects.create(title="Doomed", author=author)
    post.trash()
    assert post.is_trashed is True
    assert Post.objects.filter(pk=post.pk).exists() is False
    assert Post.objects.with_trashed().filter(pk=post.pk).exists() is True
    assert list(Post.objects.only_trashed()) == [post]


def test_trashed_post_excluded_from_published(author):
    post = Post.objects.create(title="Live", author=author, status=Status.PUBLISHED)
    assert list(Post.objects.published()) == [post]
    post.trash()
    assert list(Post.objects.published()) == []


def test_restore_brings_post_back(author):
    post = Post.objects.create(title="Back", author=author)
    post.trash()
    post.restore()
    assert post.is_trashed is False
    assert Post.objects.filter(pk=post.pk).exists() is True
    assert list(Post.objects.only_trashed()) == []


def test_trash_does_not_create_a_revision(author):
    # Soft-delete leaves content untouched, so no history snapshot is added.
    post = Post.objects.create(title="Live", author=author)
    before = post.revisions.count()
    post.trash()
    assert post.revisions.count() == before


def test_pages_support_soft_delete(author):
    page = Page.objects.create(title="About", author=author)
    page.trash()
    assert Page.objects.filter(pk=page.pk).exists() is False
    assert list(Page.objects.only_trashed()) == [page]
    page.restore()
    assert Page.objects.filter(pk=page.pk).exists() is True
