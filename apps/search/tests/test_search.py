"""Public site search over published posts and pages.

The test database is SQLite, so these exercise the DB-agnostic ``icontains``
fallback (the Postgres full-text path is gated on ``connection.vendor`` and
verified separately on a real Postgres instance).
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import translation

from apps.content.models import Page, Post, Service, Status
from apps.search.services import search_content

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def author():
    return User.objects.create_user(username="writer")


# --------------------------------------------------------------------------- #
# Service: search_content()
# --------------------------------------------------------------------------- #
def test_matches_published_post_by_title(author):
    post = Post.objects.create(
        title="Django performance tips", author=author, status=Status.PUBLISHED
    )
    results = search_content("performance", "en")
    assert post in results


def test_matches_post_by_body(author):
    post = Post.objects.create(
        title="Untitled",
        body="<p>A deep dive into caching strategies</p>",
        author=author,
        status=Status.PUBLISHED,
    )
    assert post in search_content("caching", "en")


def test_matches_published_page(author):
    page = Page.objects.create(title="About our agency", author=author, status=Status.PUBLISHED)
    assert page in search_content("agency", "en")


def test_is_case_insensitive(author):
    post = Post.objects.create(title="Scaling Postgres", author=author, status=Status.PUBLISHED)
    assert post in search_content("POSTGRES", "en")


def test_excludes_drafts(author):
    Post.objects.create(title="Secret draft topic", author=author)  # draft
    assert search_content("topic", "en") == []


def test_matches_published_service_by_title(author):
    service = Service.objects.create(
        title="Website migration service", author=author, status=Status.PUBLISHED
    )
    assert service in search_content("migration", "en")


def test_matches_published_service_by_summary(author):
    service = Service.objects.create(
        title="Audit",
        summary="We review your Lighthouse scores and fix regressions.",
        author=author,
        status=Status.PUBLISHED,
    )
    assert service in search_content("lighthouse", "en")


def test_excludes_draft_service(author):
    Service.objects.create(title="Hidden draft service", author=author)  # draft
    assert search_content("hidden", "en") == []


def test_excludes_noindex_service(author):
    Service.objects.create(
        title="Noindex service", author=author, status=Status.PUBLISHED, noindex=True
    )
    assert search_content("noindex", "en") == []


def test_excludes_noindex_content(author):
    """`noindex` items are hidden from discovery (sitemap, crawlers) and site search."""
    Post.objects.create(title="Hidden gem", author=author, status=Status.PUBLISHED, noindex=True)
    assert search_content("Hidden", "en") == []


def test_overlong_query_is_handled(author):
    """A pathologically long query must be capped and must not error."""
    Post.objects.create(title="Boundary case", author=author, status=Status.PUBLISHED)
    # No exception, returns a list (the 5000-char term matches nothing here).
    assert search_content("z" * 5000, "en") == []


def test_blank_query_returns_empty(author):
    Post.objects.create(title="Anything", author=author, status=Status.PUBLISHED)
    assert search_content("   ", "en") == []


def test_no_match_returns_empty(author):
    Post.objects.create(title="Hello world", author=author, status=Status.PUBLISHED)
    assert search_content("nonexistentterm", "en") == []


def test_searches_active_language_translation_only(author):
    """A term that only exists in the German translation must not match in English."""
    post = Post.objects.create(title="English title", author=author, status=Status.PUBLISHED)
    post.set_current_language("de")
    post.title = "Einzigartigwort"
    post.save()

    assert post not in search_content("Einzigartigwort", "en")
    assert post in search_content("Einzigartigwort", "de")


# --------------------------------------------------------------------------- #
# View: /search/?q=
# --------------------------------------------------------------------------- #
def test_search_page_lists_matching_posts(client, author):
    Post.objects.create(title="Findable headline", author=author, status=Status.PUBLISHED)
    response = client.get(reverse("search:results"), {"q": "Findable"})
    assert response.status_code == 200
    assert b"Findable headline" in response.content


def test_search_page_lists_matching_pages(client, author):
    """A matching Page renders through the results template (no excerpt field)."""
    Page.objects.create(title="Contact page", author=author, status=Status.PUBLISHED)
    response = client.get(reverse("search:results"), {"q": "Contact"})
    assert response.status_code == 200
    assert b"Contact page" in response.content


def test_search_page_without_query_renders(client):
    response = client.get(reverse("search:results"))
    assert response.status_code == 200


def test_search_page_reports_no_results(client, author):
    response = client.get(reverse("search:results"), {"q": "zzznothing"})
    assert response.status_code == 200
    assert b"No results" in response.content


def test_search_box_present_in_header(client):
    html = client.get(reverse("content:post_list")).content.decode()
    assert reverse("search:results") in html
    assert 'name="q"' in html


def test_german_search_uses_localized_url(client, author):
    post = Post.objects.create(title="Hallo Welt", author=author, status=Status.PUBLISHED)
    post.set_current_language("de")
    post.title = "Deutschartikel"
    post.save()
    with translation.override("de"):
        url = reverse("search:results")
    response = client.get(url, {"q": "Deutschartikel"})
    assert response.status_code == 200
    assert b"Deutschartikel" in response.content
