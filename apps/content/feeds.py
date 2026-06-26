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

from .models import Category
from .repositories import CategoryRepository, PostRepository

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


class CategoryPostsFeed(Feed):
    """Per-category RSS feed: a single category's published posts, newest first.

    Served (inside the i18n URL prefixes) at the category archive URL +
    ``rss.xml``. Like the site feed it holds no raw ORM — the category lookup and
    the post query both go through the repositories.
    """

    def get_object(self, request, slug: str) -> Category:
        return CategoryRepository.get_by_slug(slug)

    def title(self, obj: Category) -> str:
        return f"{obj} · {SiteSettingsRepository.get().site_name}"

    def description(self, obj: Category) -> str:
        return obj.safe_translation_getter("description", any_language=True) or (
            f"Latest posts in {obj}"
        )

    def link(self, obj: Category) -> str:
        return obj.get_absolute_url()

    def items(self, obj: Category):
        return PostRepository.published_in_category_for_feed(obj, _FEED_LIMIT)

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
