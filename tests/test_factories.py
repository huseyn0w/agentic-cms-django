"""Smoke tests for the shared factory_boy factories (tests/factories.py).

These pin the factories' core contract — a usable author and a published,
publicly-visible post — so the layer the rest of the suite leans on can't rot
silently.
"""

from __future__ import annotations

import pytest

from apps.content.models import Post, Status
from tests.factories import PostFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_user_factory_builds_authenticatable_user():
    user = UserFactory()
    assert user.pk is not None
    assert user.check_password("pw-secret-123")
    assert user.email == f"{user.username}@example.com"


def test_user_factory_accepts_explicit_password():
    user = UserFactory(password="custom-pass-999")
    assert user.check_password("custom-pass-999")


def test_post_factory_builds_a_published_post():
    post = PostFactory(title="Hello From The Factory")
    assert post.pk is not None
    assert post.status == Status.PUBLISHED
    assert post.author.pk is not None
    # Translated title round-trips and the post is publicly visible.
    assert post.title == "Hello From The Factory"
    assert post in Post.objects.published()
