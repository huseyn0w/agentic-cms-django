"""SEO core: settings singleton + <head> meta/OG/Twitter/robots/analytics."""

import pytest
from django.contrib.auth import get_user_model

from apps.content.models import Post, Status
from apps.seo.models import SeoSettings

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def author():
    return User.objects.create_user(username="writer")


@pytest.fixture
def published_post(author):
    return Post.objects.create(
        title="Hello World",
        excerpt="A short summary.",
        body="<p>Body text.</p>",
        author=author,
        status=Status.PUBLISHED,
    )


# --------------------------------------------------------------------------- #
# SeoSettings singleton
# --------------------------------------------------------------------------- #
def test_seosettings_is_a_cached_singleton():
    a = SeoSettings.load()
    b = SeoSettings.load()
    assert a.pk == 1 and b.pk == 1
    assert SeoSettings.objects.count() == 1
    a.discourage_search = True
    a.save()
    assert SeoSettings.load().discourage_search is True


# --------------------------------------------------------------------------- #
# <head> rendering on a post
# --------------------------------------------------------------------------- #
def test_post_head_has_og_twitter_canonical_robots(client, published_post):
    html = client.get(published_post.get_absolute_url()).content.decode()
    assert 'property="og:title"' in html
    assert 'property="og:description"' in html
    assert 'property="og:type" content="article"' in html
    assert 'property="og:url"' in html
    assert 'name="twitter:card"' in html
    assert 'rel="canonical"' in html
    assert 'name="robots" content="index,follow"' in html
    # Description falls back to the excerpt.
    assert "A short summary." in html


def test_meta_title_and_description_override(client, published_post):
    published_post.meta_title = "Custom SEO Title"
    published_post.meta_description = "Custom SEO description."
    published_post.save()
    html = client.get(published_post.get_absolute_url()).content.decode()
    assert "<title>Custom SEO Title" in html
    assert "Custom SEO description." in html
    assert 'content="Custom SEO Title"' in html  # og:title too


def test_post_noindex_sets_robots_noindex(client, published_post):
    published_post.noindex = True
    published_post.save()
    html = client.get(published_post.get_absolute_url()).content.decode()
    assert 'name="robots" content="noindex,nofollow"' in html


def test_discourage_search_forces_site_wide_noindex(client, published_post):
    seo = SeoSettings.load()
    seo.discourage_search = True
    seo.save()
    html = client.get(published_post.get_absolute_url()).content.decode()
    assert 'name="robots" content="noindex,nofollow"' in html


def test_canonical_field_overrides_computed_url(client, published_post):
    published_post.canonical_url = "https://example.com/canonical/"
    published_post.save()
    html = client.get(published_post.get_absolute_url()).content.decode()
    assert 'rel="canonical" href="https://example.com/canonical/"' in html


def test_og_image_renders_when_set(client, published_post):
    published_post.og_image = "seo/share.png"
    published_post.save()
    html = client.get(published_post.get_absolute_url()).content.decode()
    assert 'property="og:image"' in html
    assert "seo/share.png" in html


# --------------------------------------------------------------------------- #
# Verification + analytics (site-wide)
# --------------------------------------------------------------------------- #
def test_verification_and_analytics_tags_render(client, published_post):
    seo = SeoSettings.load()
    seo.google_site_verification = "google-verify-token"
    seo.google_analytics_id = "G-TEST12345"
    seo.save()
    html = client.get(published_post.get_absolute_url()).content.decode()
    assert 'name="google-site-verification" content="google-verify-token"' in html
    assert "G-TEST12345" in html


def test_analytics_absent_when_unset(client, published_post):
    html = client.get(published_post.get_absolute_url()).content.decode()
    assert "googletagmanager.com/gtag" not in html
    assert "google-site-verification" not in html
