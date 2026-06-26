import pytest
from django.contrib.auth import get_user_model

from apps.content.models import Post, Service, Status
from apps.core.services import home_context

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def author():
    return User.objects.create_user(username="writer", email="w@example.com")


def test_home_context_returns_only_published_posts(author):
    live = Post.objects.create(title="Live", author=author, status=Status.PUBLISHED)
    Post.objects.create(title="Draft", author=author)  # draft excluded
    ctx = home_context()
    assert list(ctx["recent_posts"]) == [live]


def test_home_context_caps_each_section_at_three(author):
    for i in range(5):
        Post.objects.create(title=f"P{i}", author=author, status=Status.PUBLISHED)
        Service.objects.create(title=f"S{i}", author=author, status=Status.PUBLISHED)
    ctx = home_context()
    assert len(ctx["recent_posts"]) == 3
    assert len(ctx["featured_services"]) == 3
