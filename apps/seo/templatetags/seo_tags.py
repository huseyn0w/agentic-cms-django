"""Template tags for the SEO <head>.

``{% seo_head obj og_type %}`` renders all the head meta in one place: title,
description, canonical, robots, Open Graph, Twitter cards, verification tags and
analytics snippets. Values are computed here (Django templates can't call methods
with arguments) and handed to seo/head.html.
"""

from __future__ import annotations

from django import template

from apps.core.models import SiteSettings
from apps.seo.models import SeoSettings

register = template.Library()


def _abs(request, url: str) -> str:
    if not url:
        return ""
    return request.build_absolute_uri(url) if request is not None else url


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
    }
