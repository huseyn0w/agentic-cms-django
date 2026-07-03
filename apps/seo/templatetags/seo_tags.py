"""Template tags for the SEO <head>.

``{% seo_head obj og_type %}`` renders all the head meta in one place: title,
description, canonical, robots, Open Graph, Twitter cards, verification tags and
analytics snippets. Values are computed here (Django templates can't call methods
with arguments) and handed to seo/head.html.
"""

from __future__ import annotations

import json

from django import template
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import get_language

from apps.core.models import SiteSettings
from apps.seo import jsonld
from apps.seo.models import SeoSettings

register = template.Library()


def _abs(request, url: str) -> str:
    if not url:
        return ""
    return request.build_absolute_uri(url) if request is not None else url


def _dump_ld(data: dict) -> str:
    """Serialise a JSON-LD node, escaping the characters that could break out of
    the surrounding <script> tag (same approach as Django's json_script)."""
    text = json.dumps(data, ensure_ascii=False)
    text = text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return mark_safe(text)  # noqa: S308 - escaped above; safe inside <script type=ld+json>


@register.inclusion_tag("seo/jsonld.html", takes_context=True)
def seo_jsonld(context, obj=None, og_type: str = "website"):
    request = context.get("request")
    seo = SeoSettings.load()
    site = SiteSettings.load()
    language = get_language() or ""

    def abs_url(url: str) -> str:
        return _abs(request, url)

    # Organization + WebSite identify the brand entity on every public page.
    nodes = [
        jsonld.organization_schema(seo, site, abs_url),
        jsonld.website_schema(seo, site, abs_url),
    ]

    if obj is not None and og_type == "article":
        nodes.append(jsonld.article_schema(obj, seo, site, abs_url, language))
        crumbs = [
            ("Home", abs_url("/")),
            ("Blog", abs_url(reverse("content:post_list"))),
            (obj.seo_title(), obj.canonical_url or abs_url(obj.get_absolute_url())),
        ]
        nodes.append(jsonld.breadcrumb_schema(crumbs))
    elif obj is not None and og_type == "service":
        nodes.append(jsonld.service_schema(obj, seo, site, abs_url))
        faq = jsonld.faqpage_schema(obj.faq_items())
        if faq:
            nodes.append(faq)
        crumbs = [
            ("Home", abs_url("/")),
            ("Services", abs_url(reverse("content:service_list"))),
            (obj.seo_title(), obj.canonical_url or abs_url(obj.get_absolute_url())),
        ]
        nodes.append(jsonld.breadcrumb_schema(crumbs))
    elif obj is not None and og_type == "profile":
        profile = jsonld.profilepage_schema(obj, abs_url, obj.get_absolute_url())
        if profile:
            nodes.append(profile)
        crumbs = [
            ("Home", abs_url("/")),
            (obj.display_name, abs_url(obj.get_absolute_url())),
        ]
        nodes.append(jsonld.breadcrumb_schema(crumbs))
    elif obj is not None:
        crumbs = [
            ("Home", abs_url("/")),
            (obj.seo_title(), obj.canonical_url or abs_url(obj.get_absolute_url())),
        ]
        nodes.append(jsonld.breadcrumb_schema(crumbs))

    return {"jsonld_blocks": [_dump_ld(node) for node in nodes]}


@register.inclusion_tag("seo/head.html", takes_context=True)
def seo_head(context, obj=None, og_type: str = "website"):
    request = context.get("request")
    seo = SeoSettings.load()
    # Load SiteSettings explicitly: some pages (e.g. allauth) put a contrib.sites
    # Site object in the `site` context var, which would shadow our settings.
    site = SiteSettings.load()
    site_name = (seo.og_site_name or site.site_name).strip()
    current_url = _abs(request, request.path) if request is not None else ""

    if obj is not None:
        title = obj.seo_title()
        description = obj.seo_description()
        canonical = obj.canonical_url or current_url
        robots = obj.seo_robots(seo)
        og_image = _abs(request, obj.og_image_url())
    else:
        title = site_name
        description = (seo.default_meta_description or site.tagline or "").strip()
        canonical = current_url
        robots = "noindex,nofollow" if seo.discourage_search else "index,follow"
        og_image = ""

    if not og_image and seo.default_og_image:
        og_image = _abs(request, seo.default_og_image.url)

    # article:published_time and article:author — only on article pages.
    article_published_time = ""
    article_author = ""
    if og_type == "article" and obj is not None:
        pub = getattr(obj, "published_at", None) or getattr(obj, "created_at", None)
        if pub:
            article_published_time = pub.isoformat()
        author = getattr(obj, "author", None)
        if author is not None:
            author_url = getattr(author, "get_absolute_url", None)
            if author_url is not None:
                article_author = _abs(request, author_url())
            else:
                article_author = getattr(author, "display_name", "") or str(author)

    return {
        "seo": seo,
        "og_type": og_type,
        "seo_title": title,
        "seo_description": description,
        "seo_canonical": canonical,
        "seo_robots": robots,
        "seo_og_image": og_image,
        "seo_site_name": site_name,
        "seo_locale": context.get("i18n_current_language", ""),
        "seo_article_published_time": article_published_time,
        "seo_article_author": article_author,
    }
