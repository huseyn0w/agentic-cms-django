"""F3 — RSS feed for published posts."""

import pytest
from django.contrib.auth import get_user_model

from apps.content.models import Post, Status

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
