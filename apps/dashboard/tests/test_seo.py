"""Dashboard SEO editing: SeoSettings page + per-content SEO fields."""

import pytest
from django.urls import reverse

from apps.content.models import Post
from apps.seo.models import SeoSettings

pytestmark = pytest.mark.django_db


def test_admin_edits_seo_settings(client, make_user):
    client.force_login(make_user("admin", role="Administrator"))
    response = client.post(
        reverse("dashboard:seo_settings"),
        {
            "og_site_name": "My Brand",
            "default_meta_description": "Default desc.",
            "twitter_handle": "@brand",
            "google_analytics_id": "G-ABC123",
            "google_tag_manager_id": "",
            "google_site_verification": "verify-token",
            "bing_site_verification": "",
            "discourage_search": "on",
        },
    )
    assert response.status_code == 302
    seo = SeoSettings.load()
    assert seo.og_site_name == "My Brand"
    assert seo.google_analytics_id == "G-ABC123"
    assert seo.discourage_search is True


def test_seo_settings_rejects_malformed_analytics_id(client, make_user):
    client.force_login(make_user("admin", role="Administrator"))
    response = client.post(
        reverse("dashboard:seo_settings"),
        {"google_analytics_id": "not-an-id", "discourage_search": ""},
    )
    assert response.status_code == 200  # re-renders with errors, not saved
    assert SeoSettings.load().google_analytics_id == ""


def test_seo_settings_page_requires_manage_settings(client, make_user):
    # Authors lack manage_settings -> denied.
    client.force_login(make_user("author", role="Author"))
    assert client.get(reverse("dashboard:seo_settings")).status_code == 403


def test_post_editor_saves_seo_fields(client, make_user):
    client.force_login(make_user("admin", role="Administrator"))
    client.post(
        reverse("dashboard:post_create"),
        {
            "title": "Hello",
            "body": "<p>x</p>",
            "status": "published",
            "meta_title": "SEO Title",
            "meta_description": "SEO desc.",
            "canonical_url": "https://example.com/c/",
            "noindex": "on",
        },
    )
    post = Post.objects.language("en").get(slug="hello")
    assert post.meta_title == "SEO Title"
    assert post.meta_description == "SEO desc."
    assert post.canonical_url == "https://example.com/c/"
    assert post.noindex is True
