"""F3 — RSS feed for published posts."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.content.models import Category, Post, Status

User = get_user_model()
pytestmark = pytest.mark.django_db
RSS_URL = "/rss.xml"


@pytest.fixture
def author():
    return User.objects.create_user(username="writer", email="w@example.com")


def test_rss_feed_is_served(client):
    resp = client.get(RSS_URL)
    assert resp.status_code == 200
    assert "rss" in resp["Content-Type"]


def test_rss_includes_published_posts(client, author):
    Post.objects.create(title="Live in feed", author=author, status=Status.PUBLISHED)
    body = client.get(RSS_URL).content.decode()
    assert "Live in feed" in body


def test_rss_excludes_drafts(client, author):
    Post.objects.create(title="Draft hidden", author=author)  # draft
    body = client.get(RSS_URL).content.decode()
    assert "Draft hidden" not in body


# --- Per-category RSS feed --------------------------------------------------


@pytest.fixture
def category():
    return Category.objects.create(name="Engineering", slug="engineering")


def _category_feed_url(slug: str) -> str:
    return reverse("content:category_rss", args=[slug])


def test_category_feed_is_served(client, category):
    resp = client.get(_category_feed_url(category.slug))
    assert resp.status_code == 200
    assert "rss" in resp["Content-Type"]


def test_category_feed_includes_published_post_in_category(client, author, category):
    post = Post.objects.create(title="Filed post", author=author, status=Status.PUBLISHED)
    post.categories.add(category)
    body = client.get(_category_feed_url(category.slug)).content.decode()
    assert "Filed post" in body


def test_category_feed_excludes_post_in_other_category(client, author, category):
    other = Category.objects.create(name="Design", slug="design")
    elsewhere = Post.objects.create(title="Elsewhere post", author=author, status=Status.PUBLISHED)
    elsewhere.categories.add(other)
    body = client.get(_category_feed_url(category.slug)).content.decode()
    assert "Elsewhere post" not in body


def test_category_feed_excludes_draft_in_category(client, author, category):
    draft = Post.objects.create(title="Draft in category", author=author)  # draft
    draft.categories.add(category)
    body = client.get(_category_feed_url(category.slug)).content.decode()
    assert "Draft in category" not in body


def test_category_feed_excludes_trashed_post_in_category(client, author, category):
    trashed = Post.objects.create(
        title="Trashed in category", author=author, status=Status.PUBLISHED
    )
    trashed.categories.add(category)
    trashed.trash()
    body = client.get(_category_feed_url(category.slug)).content.decode()
    assert "Trashed in category" not in body
