"""schema.org JSON-LD structured data rendering."""

import json
import re

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.content.models import Post, Status
from apps.seo.models import SeoSettings

User = get_user_model()
pytestmark = pytest.mark.django_db

LD_BLOCK = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL)


def _ld_nodes(html: str) -> list[dict]:
    return [json.loads(m) for m in LD_BLOCK.findall(html)]


def _types(nodes: list[dict]) -> set[str]:
    return {n.get("@type") for n in nodes}


@pytest.fixture
def author():
    return User.objects.create_user(username="writer", first_name="Ada", last_name="Lovelace")


@pytest.fixture
def published_post(author):
    return Post.objects.create(
        title="Hello World",
        excerpt="A short summary.",
        body="<p>Body.</p>",
        author=author,
        status=Status.PUBLISHED,
    )


def test_home_emits_organization_and_website(client):
    nodes = _ld_nodes(client.get("/").content.decode())
    assert "Organization" in _types(nodes)
    assert "WebSite" in _types(nodes)


def test_post_emits_article_person_breadcrumb(client, published_post):
    nodes = _ld_nodes(client.get(published_post.get_absolute_url()).content.decode())
    types = _types(nodes)
    assert {"Organization", "WebSite", "Article", "BreadcrumbList"} <= types

    article = next(n for n in nodes if n.get("@type") == "Article")
    assert article["headline"] == "Hello World"
    assert article["description"] == "A short summary."
    assert article["datePublished"]
    assert article["author"]["@type"] == "Person"
    assert article["author"]["name"]  # display name
    assert article["publisher"]["@type"] == "Organization"
    assert article["mainEntityOfPage"]["@id"].endswith(published_post.get_absolute_url())

    crumbs = next(n for n in nodes if n.get("@type") == "BreadcrumbList")
    names = [i["name"] for i in crumbs["itemListElement"]]
    assert names[0] == "Home"
    assert names[-1] == "Hello World"
    # positions are 1-based and ordered
    assert [i["position"] for i in crumbs["itemListElement"]] == [1, 2, 3]


def test_sameas_from_social_profiles(client, published_post):
    seo = SeoSettings.load()
    seo.social_profiles = "https://twitter.com/brand\n\nhttps://www.linkedin.com/company/brand\n"
    seo.save()
    nodes = _ld_nodes(client.get("/").content.decode())
    org = next(n for n in nodes if n.get("@type") == "Organization")
    assert org["sameAs"] == [
        "https://twitter.com/brand",
        "https://www.linkedin.com/company/brand",
    ]


def test_jsonld_escapes_html_to_prevent_script_breakout(client, author):
    post = Post.objects.create(
        title="Pwn</script><script>alert(1)</script>",
        author=author,
        status=Status.PUBLISHED,
    )
    html = client.get(post.get_absolute_url()).content.decode()
    # Assert on the RAW html (not regex-captured blocks, which would truncate at an
    # injected </script>): the breakout sequence must never appear, and the payload
    # must be present only in its <-escaped form.
    assert "<script>alert(1)" not in html
    assert "</script><script>" not in html
    assert "\\u003cscript\\u003ealert(1)" in html
    # And the structured data still parses with the payload preserved as text.
    article = next(n for n in _ld_nodes(html) if n.get("@type") == "Article")
    assert "alert(1)" in article["headline"]


def test_dashboard_has_no_jsonld(client, published_post):
    # Use the public list page to confirm the article block is only on detail pages.
    html = client.get(reverse("content:post_list")).content.decode()
    assert "Article" not in _types(_ld_nodes(html))
