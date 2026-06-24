"""RSS feed for published posts (FEATURE_MATRIX F3).

A thin ``django.contrib.syndication`` Feed. All data access goes through the
repositories (the feed holds no raw ORM), consistent with the project's layering.
Served at ``/rss.xml`` (root, outside the i18n URL prefixes).
"""

from __future__ import annotations

from django.contrib.syndication.views import Feed
from django.urls import reverse
from django.utils.html import strip_tags

from apps.core.repositories import SiteSettingsRepository

from .repositories import PostRepository

_FEED_LIMIT = 20


class LatestPostsFeed(Feed):
    def title(self) -> str:
        return SiteSettingsRepository.get().site_name

    def description(self) -> str:
        site = SiteSettingsRepository.get()
        return site.tagline or f"Latest posts from {site.site_name}"

    def link(self) -> str:
        return reverse("content:post_list")

    def items(self):
        return PostRepository.for_feed(_FEED_LIMIT)

    def item_title(self, item) -> str:
        return item.title

    def item_description(self, item) -> str:
        return item.excerpt or strip_tags(item.body or "")[:300]

    def item_link(self, item) -> str:
        return item.get_absolute_url()

    def item_pubdate(self, item):
        return item.published_at

    def item_author_name(self, item) -> str | None:
        return item.author.display_name if item.author else None
