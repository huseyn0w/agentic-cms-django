"""Post likes (F6): repository toggle, service, and the public endpoint."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.content import services
from apps.content.models import Like, Post, Status
from apps.content.repositories import LikeRepository

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def reader():
    return User.objects.create_user(username="reader", password="pw", email="r@example.com")


@pytest.fixture
def post():
    return Post.objects.create(title="Likeable", status=Status.PUBLISHED)


# --------------------------------------------------------------------------- #
# Repository / service
# --------------------------------------------------------------------------- #
def test_toggle_likes_then_unlikes(post, reader):
    liked, count = services.toggle_post_like(post, reader)
    assert liked is True
    assert count == 1
    assert LikeRepository.is_liked_by(post, reader) is True

    liked, count = services.toggle_post_like(post, reader)
    assert liked is False
    assert count == 0
    assert LikeRepository.is_liked_by(post, reader) is False


def test_like_is_idempotent_per_user(post, reader):
    Like.objects.create(post=post, user=reader)
    # A duplicate toggle removes it rather than raising on the unique constraint.
    liked, count = services.toggle_post_like(post, reader)
    assert liked is False
    assert count == 0


def test_is_liked_by_anonymous_is_false(post):
    from django.contrib.auth.models import AnonymousUser

    assert LikeRepository.is_liked_by(post, AnonymousUser()) is False


# --------------------------------------------------------------------------- #
# Endpoint
# --------------------------------------------------------------------------- #
def test_like_endpoint_toggles_for_authenticated_user(client, post, reader):
    client.force_login(reader)
    url = reverse("content:post_like", args=[post.slug])
    response = client.post(url)
    assert response.status_code == 302
    assert post.likes.count() == 1
    # Toggling again removes it.
    client.post(url)
    assert post.likes.count() == 0


def test_like_endpoint_requires_login(client, post):
    url = reverse("content:post_like", args=[post.slug])
    response = client.post(url)
    assert response.status_code == 302
    assert reverse("account_login") in response.url
    assert post.likes.count() == 0


def test_like_endpoint_rejects_get(client, post, reader):
    client.force_login(reader)
    response = client.get(reverse("content:post_like", args=[post.slug]))
    assert response.status_code == 405


def test_like_count_shown_on_post_detail(client, post, reader):
    client.force_login(reader)
    client.post(reverse("content:post_like", args=[post.slug]))
    response = client.get(post.get_absolute_url())
    assert response.status_code == 200
    assert b"aria-pressed" in response.content
