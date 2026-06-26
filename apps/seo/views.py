"""Machine-readable surfaces: robots.txt, llms.txt, llms-full.txt.

All three are rendered dynamically so they reflect live content and the SEO
settings (AI-crawler policy, discourage-search). They're served at the site root,
outside the i18n URL prefixes. The views are thin: they parse request specifics and
return the body assembled by ``apps.seo.services``.
"""

from __future__ import annotations

from django.http import HttpResponse
from django.urls import reverse

from . import services

_PLAIN = "text/plain; charset=utf-8"
_MARKDOWN = "text/markdown; charset=utf-8"


def robots_txt(request) -> HttpResponse:
    sitemap_url = request.build_absolute_uri(reverse("sitemap"))
    return HttpResponse(services.robots_txt_body(sitemap_url), content_type=_PLAIN)


def llms_txt(request) -> HttpResponse:
    return HttpResponse(services.llms_txt_body(request.build_absolute_uri), content_type=_MARKDOWN)


def llms_full_txt(request) -> HttpResponse:
    return HttpResponse(
        services.llms_full_txt_body(request.build_absolute_uri), content_type=_MARKDOWN
    )
