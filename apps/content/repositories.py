"""Content data-access layer (repositories).

The single home for content ORM access. Services call these thin repository
methods; they never touch ``Model.objects`` directly. Repositories wrap the
models' custom Managers/QuerySets (``PublishableQuerySet.published()`` etc.) and
encapsulate ``select_related``/``prefetch_related`` tuning so query shape lives in
one place. Raising ``Http404`` here is a not-found signal, not business logic.
"""

from __future__ import annotations

from django.db.models import Count, QuerySet
from django.shortcuts import get_object_or_404

from .models import Category, Page, Post, Service, Tag


class PostRepository:
    @staticmethod
    def published() -> QuerySet:
        return (
            Post.objects.published()
            .select_related("author")
            .prefetch_related("categories", "tags")
        )

    @staticmethod
    def published_in_category(category: Category) -> QuerySet:
        return PostRepository.published().filter(categories=category)

    @staticmethod
    def published_with_tag(tag: Tag) -> QuerySet:
        return PostRepository.published().filter(tags=tag)

    @staticmethod
    def recent_published(limit: int) -> QuerySet:
        return (
            Post.objects.published()
            .select_related("author")
            .prefetch_related("categories")[:limit]
        )

    @staticmethod
    def get_by_slug(slug: str) -> Post:
        return get_object_or_404(
            Post.objects.select_related("author").prefetch_related("categories", "tags"),
            slug=slug,
        )

    # -- Dashboard (admin) queries -- #
    @staticmethod
    def for_dashboard(user, status: str | None = None, search: str | None = None) -> QuerySet:
        """Posts the dashboard lists for ``user`` (owner-scoped), optionally filtered.

        ``status``/``search`` are assumed pre-validated by the service. Title search
        goes through the parler translation table.
        """
        qs = Post.objects.editable_by(user).select_related("author")
        if status:
            qs = qs.filter(status=status)
        if search:
            qs = qs.filter(translations__title__icontains=search).distinct()
        return qs

    @staticmethod
    def recent_editable(user, limit: int) -> QuerySet:
        return Post.objects.editable_by(user).select_related("author")[:limit]

    @staticmethod
    def count_all() -> int:
        return Post.objects.count()

    @staticmethod
    def published_indexable(limit: int) -> QuerySet:
        """Published, non-noindex posts for crawler surfaces (llms.txt), capped."""
        return (
            Post.objects.published()
            .filter(noindex=False)
            .select_related("author")[:limit]
        )

    @staticmethod
    def for_feed(limit: int) -> QuerySet:
        """Most-recent published posts for the RSS/Atom feed (translations prefetched)."""
        return (
            Post.objects.published()
            .select_related("author")
            .prefetch_related("translations")[:limit]
        )


class PageRepository:
    @staticmethod
    def get_by_slug(slug: str) -> Page:
        return get_object_or_404(Page, slug=slug)

    @staticmethod
    def all_for_admin() -> QuerySet:
        # Models lost their Meta ordering (it referenced now-translated fields), so
        # order on a shared field here for stable pagination.
        return Page.objects.select_related("author").order_by("-created_at")

    @staticmethod
    def count_all() -> int:
        return Page.objects.count()

    @staticmethod
    def published_indexable(limit: int) -> QuerySet:
        return Page.objects.published().filter(noindex=False)[:limit]


class ServiceRepository:
    @staticmethod
    def published() -> QuerySet:
        return Service.objects.published()

    @staticmethod
    def recent_published(limit: int) -> QuerySet:
        return Service.objects.published()[:limit]

    @staticmethod
    def get_by_slug(slug: str) -> Service:
        return get_object_or_404(Service, slug=slug)

    @staticmethod
    def all_for_admin() -> QuerySet:
        return Service.objects.select_related("author").order_by("-created_at")

    @staticmethod
    def published_indexable(limit: int) -> QuerySet:
        return Service.objects.published().filter(noindex=False)[:limit]


class CategoryRepository:
    @staticmethod
    def get_by_slug(slug: str) -> Category:
        return get_object_or_404(Category, slug=slug)

    @staticmethod
    def with_post_counts() -> QuerySet:
        return (
            Category.objects.select_related("parent")
            .annotate(post_count=Count("posts"))
            .order_by("slug")
        )


class TagRepository:
    @staticmethod
    def get_by_slug(slug: str) -> Tag:
        return get_object_or_404(Tag, slug=slug)

    @staticmethod
    def with_post_counts() -> QuerySet:
        return Tag.objects.annotate(post_count=Count("posts")).order_by("slug")
