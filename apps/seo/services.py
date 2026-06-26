"""SEO machine-readable surface services: robots.txt, llms.txt, llms-full.txt.

The views parse request specifics (the sitemap URL, an absolute-URI builder) and
pass them in as primitives/callables; this module assembles the text bodies and
reads data only through repositories.
"""

from __future__ import annotations

from collections.abc import Callable

from django.utils.html import strip_tags

from apps.content.repositories import PageRepository, PostRepository, ServiceRepository
from apps.core.repositories import SiteSettingsRepository

from .constants import AI_CRAWLER_USER_AGENTS
from .repositories import SeoSettingsRepository

# Private areas that should never be crawled regardless of policy.
DISALLOWED_PATHS = ["/dashboard/", "/accounts/", "/admin/", "/library/"]

# Cap how many items the llms.txt files list/inline, to bound response size.
LLMS_MAX_ITEMS = 100


def robots_txt_body(sitemap_url: str) -> str:
    """Build robots.txt honouring the discourage-search and AI-crawler toggles."""
    seo = SeoSettingsRepository.get()
    lines: list[str] = []

    if seo.discourage_search:
        # Staging / private: ask everyone to stay out, advertise no sitemap.
        lines += ["User-agent: *", "Disallow: /"]
        return "\n".join(lines) + "\n"

    lines += ["User-agent: *"]
    lines += [f"Disallow: {path}" for path in DISALLOWED_PATHS]
    lines += [""]

    # Explicit, grouped policy for the answer-engine crawlers. A named-bot group
    # overrides the "*" group entirely, so repeat the private-path Disallows here
    # (most-specific rule wins, so "Allow: /" still opens the rest of the site).
    lines += ["# AI answer-engine crawlers"]
    for agent in AI_CRAWLER_USER_AGENTS:
        lines += [f"User-agent: {agent}"]
        if seo.allow_ai_crawlers:
            lines += [f"Disallow: {path}" for path in DISALLOWED_PATHS]
            lines += ["Allow: /", ""]
        else:
            lines += ["Disallow: /", ""]

    lines += [f"Sitemap: {sitemap_url}"]
    return "\n".join(lines) + "\n"


def _summary() -> str:
    site = SiteSettingsRepository.get()
    seo = SeoSettingsRepository.get()
    return (seo.default_meta_description or site.tagline or "").strip()


def llms_txt_body(build_uri: Callable[[str], str]) -> str:
    """A concise, link-first index of the site (see llmstxt.org)."""
    site = SiteSettingsRepository.get()
    out: list[str] = [f"# {site.site_name}"]
    summary = _summary()
    if summary:
        out += ["", f"> {summary}"]

    sections = (
        ("Services", ServiceRepository.published_indexable(LLMS_MAX_ITEMS)),
        ("Pages", PageRepository.published_indexable(LLMS_MAX_ITEMS)),
        ("Blog", PostRepository.published_indexable(LLMS_MAX_ITEMS)),
    )
    for title, items in sections:
        rendered = list(items)
        if not rendered:
            continue
        out += ["", f"## {title}"]
        for obj in rendered:
            url = build_uri(obj.get_absolute_url())
            desc = obj.seo_description()
            out += [f"- [{obj.seo_title()}]({url})" + (f": {desc}" if desc else "")]

    return "\n".join(out) + "\n"


def llms_full_txt_body(build_uri: Callable[[str], str]) -> str:
    """Like llms.txt but with the full, plain-text content inlined for direct reading."""
    site = SiteSettingsRepository.get()
    out: list[str] = [f"# {site.site_name}"]
    summary = _summary()
    if summary:
        out += ["", f"> {summary}"]

    sections = (
        ("Services", ServiceRepository.published_indexable(LLMS_MAX_ITEMS)),
        ("Pages", PageRepository.published_indexable(LLMS_MAX_ITEMS)),
        ("Blog", PostRepository.published_indexable(LLMS_MAX_ITEMS)),
    )
    for title, items in sections:
        rendered = list(items)
        if not rendered:
            continue
        out += ["", f"# {title}"]
        for obj in rendered:
            url = build_uri(obj.get_absolute_url())
            out.extend(["", f"## {obj.seo_title()}", f"URL: {url}", ""])
            body = strip_tags(getattr(obj, "body", "") or "").strip()
            out.append(body if body else obj.seo_description())

    return "\n".join(out) + "\n"
