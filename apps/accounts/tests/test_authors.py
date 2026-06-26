"""Public author archive page + ProfilePage JSON-LD (F10)."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.content.models import Post, Status

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def author():
    return User.objects.create_user(
        username="jane",
        email="secret@example.com",
        first_name="Jane",
        last_name="Doe",
        bio="Writes about things.",
        website="https://jane.example",
    )


def test_author_page_shows_bio_and_published_posts(client, author):
    Post.objects.create(title="Her post", author=author, status=Status.PUBLISHED)
    response = client.get(reverse("accounts:author_detail", args=[author.pk]))
    assert response.status_code == 200
    assert b"Jane Doe" in response.content
    assert b"Writes about things." in response.content
    assert b"Her post" in response.content


def test_author_page_emits_profilepage_jsonld(client, author):
    Post.objects.create(title="Her post", author=author, status=Status.PUBLISHED)
    response = client.get(reverse("accounts:author_detail", args=[author.pk]))
    assert b"ProfilePage" in response.content
    assert b"https://jane.example" in response.content


def test_author_email_is_never_exposed(client, author):
    Post.objects.create(title="Her post", author=author, status=Status.PUBLISHED)
    response = client.get(reverse("accounts:author_detail", args=[author.pk]))
    assert b"secret@example.com" not in response.content


def test_user_without_published_posts_is_404(client, author):
    # Only a draft → not a public author.
    Post.objects.create(title="Draft", author=author, status=Status.DRAFT)
    response = client.get(reverse("accounts:author_detail", args=[author.pk]))
    assert response.status_code == 404


def test_unknown_author_is_404(client):
    response = client.get(reverse("accounts:author_detail", args=[9999]))
    assert response.status_code == 404
