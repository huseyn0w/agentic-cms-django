"""Builders for schema.org JSON-LD structured data.

Each function returns a plain dict (a single schema.org node). The seo_jsonld
template tag assembles the right set for a page and serialises them safely. Keeping
this as pure dict-building (no request/template coupling beyond an absolute-URL
helper passed in) makes the schemas easy to unit-test and reuse.
"""

from __future__ import annotations

from collections.abc import Callable


def organization_schema(seo, site, abs_url: Callable[[str], str]) -> dict:
    name = (seo.og_site_name or site.site_name).strip()
    data: dict = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": name,
        "url": abs_url("/"),
    }
    logo = seo.organization_logo or seo.default_og_image
    if logo:
        data["logo"] = abs_url(logo.url)
    same_as = seo.social_profile_list()
    if same_as:
        data["sameAs"] = same_as
    return data


def website_schema(seo, site, abs_url: Callable[[str], str]) -> dict:
    name = (seo.og_site_name or site.site_name).strip()
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": name,
        "url": abs_url("/"),
    }


def person_schema(author) -> dict | None:
    if author is None:
        return None
    name = getattr(author, "display_name", "") or getattr(author, "get_username", lambda: "")()
    if not name:
        return None
    return {"@type": "Person", "name": name}


def article_schema(post, seo, site, abs_url: Callable[[str], str], language: str = "") -> dict:
    data: dict = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": post.seo_title(),
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": post.canonical_url or abs_url(post.get_absolute_url()),
        },
        "url": abs_url(post.get_absolute_url()),
    }
    description = post.seo_description()
    if description:
        data["description"] = description
    image = post.og_image_url() or (seo.default_og_image.url if seo.default_og_image else "")
    if image:
        data["image"] = abs_url(image)
    if post.published_at:
        data["datePublished"] = post.published_at.isoformat()
    if post.updated_at:
        data["dateModified"] = post.updated_at.isoformat()
    person = person_schema(getattr(post, "author", None))
    if person:
        data["author"] = person
    publisher: dict = {
        "@type": "Organization",
        "name": (seo.og_site_name or site.site_name).strip(),
    }
    logo = seo.organization_logo or seo.default_og_image
    if logo:
        publisher["logo"] = {"@type": "ImageObject", "url": abs_url(logo.url)}
    data["publisher"] = publisher
    if language:
        data["inLanguage"] = language
    return data


def breadcrumb_schema(items: list[tuple[str, str]]) -> dict:
    """items: ordered [(name, absolute_url), ...] from site root to current page."""
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": name, "item": url}
            for i, (name, url) in enumerate(items, start=1)
        ],
    }
