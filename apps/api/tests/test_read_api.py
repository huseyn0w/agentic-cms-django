"""Public read API + health probes (F12a)."""

import pytest
from django.contrib.auth import get_user_model

from apps.content.models import Category, Page, Post, Service, Status

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def author():
    return User.objects.create_user(username="jane", first_name="Jane", last_name="Doe")


# --------------------------------------------------------------------------- #
# Posts
# --------------------------------------------------------------------------- #
def test_post_list_returns_only_published(client, author):
    cat = Category.objects.create(slug="news")
    cat.set_current_language("en")
    cat.name = "News"
    cat.save()
    live = Post.objects.create(title="Live", excerpt="Hi", author=author, status=Status.PUBLISHED)
    live.categories.add(cat)
    Post.objects.create(title="Draft", author=author, status=Status.DRAFT)

    data = client.get("/api/v1/posts/").json()
    assert data["count"] == 1
    row = data["results"][0]
    assert row["title"] == "Live"
    assert row["author"]["name"] == "Jane Doe"
    assert row["categories"] == [{"slug": "news", "name": "News"}]
    assert "body" not in row  # list omits body


def test_post_detail_includes_body(client, author):
    Post.objects.create(title="Deep", body="<p>full</p>", author=author, status=Status.PUBLISHED)
    data = client.get("/api/v1/posts/deep/").json()
    assert data["title"] == "Deep"
    assert data["body"] == "<p>full</p>"


def test_draft_post_detail_is_404(client, author):
    Post.objects.create(title="Secret", slug="secret", author=author, status=Status.DRAFT)
    assert client.get("/api/v1/posts/secret/").status_code == 404


def test_post_language_override(client, author):
    post = Post.objects.create(title="Hello", author=author, status=Status.PUBLISHED)
    post.set_current_language("de")
    post.title = "Hallo"
    post.save()
    data = client.get("/api/v1/posts/?lang=de").json()
    assert data["results"][0]["title"] == "Hallo"


# --------------------------------------------------------------------------- #
# Pages / services / taxonomy
# --------------------------------------------------------------------------- #
def test_page_detail(client):
    Page.objects.create(title="About", slug="about", body="<p>us</p>", status=Status.PUBLISHED)
    data = client.get("/api/v1/pages/about/").json()
    assert data["title"] == "About"
    assert data["body"] == "<p>us</p>"


def test_service_detail_includes_faq(client):
    Service.objects.create(
        title="SEO",
        slug="seo",
        summary="We do SEO.",
        status=Status.PUBLISHED,
        faq="Q: How?\nA: Well.",
    )
    data = client.get("/api/v1/services/seo/").json()
    assert data["summary"] == "We do SEO."
    assert data["faq"] == [{"question": "How?", "answer": "Well."}]


def test_page_list(client):
    Page.objects.create(title="About", slug="about", status=Status.PUBLISHED)
    data = client.get("/api/v1/pages/").json()
    assert data["results"][0]["slug"] == "about"


def test_service_list(client):
    Service.objects.create(title="SEO", slug="seo", status=Status.PUBLISHED)
    data = client.get("/api/v1/services/").json()
    assert data["results"][0]["slug"] == "seo"


def test_tags_list(client):
    from apps.content.models import Tag

    tag = Tag.objects.create(slug="django")
    tag.set_current_language("en")
    tag.name = "Django"
    tag.save()
    data = client.get("/api/v1/tags/").json()
    assert data["results"][0]["slug"] == "django"
    assert data["results"][0]["url"].endswith("/tag/django/")


def test_categories_list(client):
    cat = Category.objects.create(slug="news")
    cat.set_current_language("en")
    cat.name = "News"
    cat.save()
    data = client.get("/api/v1/categories/").json()
    assert data["results"][0]["slug"] == "news"


# --------------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------------- #
def test_health_is_ok(client):
    assert client.get("/health/").json() == {"status": "ok"}


def test_readiness_reports_database(client):
    data = client.get("/health/ready/").json()
    assert data["status"] == "ok"
    assert data["database"] is True
