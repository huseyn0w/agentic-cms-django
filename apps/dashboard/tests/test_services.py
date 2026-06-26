import pytest
from django.contrib.auth import get_user_model

from apps.comments.models import Comment, CommentStatus
from apps.content.models import Page, Post, Status
from apps.dashboard.services import (
    dashboard_stats,
    list_comments,
    list_posts,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


def test_dashboard_stats_counts_each_content_type():
    author = User.objects.create_user(username="a", email="a@example.com")
    Post.objects.create(title="P1", author=author)
    Post.objects.create(title="P2", author=author)
    Page.objects.create(title="About", author=author)

    stats = dashboard_stats()

    assert stats["posts"] == 2
    assert stats["pages"] == 1
    assert stats["media"] == 0
    assert stats["users"] == 1  # the author


def test_dashboard_stats_returns_expected_keys():
    assert set(dashboard_stats().keys()) == {"posts", "pages", "media", "users"}


@pytest.fixture
def manager():
    return User.objects.create_superuser(username="boss", email="b@example.com", password="pw")


def test_list_posts_filters_by_valid_status(manager):
    Post.objects.create(title="Draft", author=manager)
    live = Post.objects.create(title="Live", author=manager, status=Status.PUBLISHED)
    result = list_posts(manager, status=Status.PUBLISHED)
    assert list(result) == [live]


def test_list_posts_ignores_unknown_status(manager):
    Post.objects.create(title="Draft", author=manager)
    Post.objects.create(title="Live", author=manager, status=Status.PUBLISHED)
    # An unrecognised status must not filter anything out (treated as "all").
    assert list_posts(manager, status="bogus").count() == 2


def test_list_posts_searches_translated_title(manager):
    Post.objects.create(title="Caching tips", author=manager)
    Post.objects.create(title="Unrelated", author=manager)
    result = list_posts(manager, search="caching")
    assert [p.slug for p in result] == ["caching-tips"]


def test_list_comments_filters_by_valid_status(manager):
    post = Post.objects.create(title="P", author=manager)
    Comment.objects.create(post=post, name="a", body="x", status=CommentStatus.PENDING)
    spam = Comment.objects.create(post=post, name="b", body="y", status=CommentStatus.SPAM)
    result = list_comments(CommentStatus.SPAM)
    assert list(result) == [spam]


def test_list_comments_ignores_unknown_status(manager):
    post = Post.objects.create(title="P", author=manager)
    Comment.objects.create(post=post, name="a", body="x")
    assert list_comments("bogus").count() == 1
