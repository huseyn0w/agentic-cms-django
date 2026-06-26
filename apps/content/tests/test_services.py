import pytest
from django.contrib.auth.models import AnonymousUser
from django.http import Http404

from apps.content.models import Page, Post, Service, Status
from apps.content.services import (
    get_page_for_view,
    get_post_for_view,
    get_service_for_view,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def author(django_user_model):
    return django_user_model.objects.create_user(username="writer", email="w@example.com")


def test_get_post_for_view_returns_published_to_anonymous(author):
    post = Post.objects.create(title="Live", author=author, status=Status.PUBLISHED)
    assert get_post_for_view(post.slug, AnonymousUser()) == post


def test_get_post_for_view_hides_draft_from_anonymous(author):
    post = Post.objects.create(title="Secret", author=author)  # draft
    with pytest.raises(Http404):
        get_post_for_view(post.slug, AnonymousUser())


def test_get_page_for_view_hides_draft_from_anonymous(author):
    page = Page.objects.create(title="Hidden page", author=author)  # draft
    with pytest.raises(Http404):
        get_page_for_view(page.slug, AnonymousUser())


def test_get_service_for_view_hides_draft_from_anonymous(author):
    service = Service.objects.create(title="Hidden service", author=author)  # draft
    with pytest.raises(Http404):
        get_service_for_view(service.slug, AnonymousUser())
