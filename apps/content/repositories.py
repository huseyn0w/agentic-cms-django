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

from .models import Category, Like, Page, Post, Service, Tag


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

    # -- Soft-delete / trash (owner-scoped, mirrors for_dashboard) -- #
    @staticmethod
    def get_editable(user, pk: int) -> Post:
        """A live post ``user`` may manage, or Http404."""
        return get_object_or_404(Post.objects.editable_by(user), pk=pk)

    @staticmethod
    def trashed_for_dashboard(user) -> QuerySet:
        """Trashed posts ``user`` may manage (owner-scoped), newest-deleted first."""
        return (
            Post.objects.only_trashed()
            .editable_by(user)
            .select_related("author")
            .order_by("-deleted_at")
        )

    @staticmethod
    def get_trashed_editable(user, pk: int) -> Post:
        """A trashed post ``user`` may manage, or Http404 (restore/destroy target)."""
        return get_object_or_404(Post.objects.only_trashed().editable_by(user), pk=pk)

    @staticmethod
    def permanently_delete(post: Post) -> None:
        post.delete()

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

    # -- Soft-delete / trash (pages have no owner scope) -- #
    @staticmethod
    def get_for_admin(pk: int) -> Page:
        """A live page, or Http404."""
        return get_object_or_404(Page, pk=pk)

    @staticmethod
    def trashed_for_admin() -> QuerySet:
        return Page.objects.only_trashed().select_related("author").order_by("-deleted_at")

    @staticmethod
    def get_trashed(pk: int) -> Page:
        return get_object_or_404(Page.objects.only_trashed(), pk=pk)

    @staticmethod
    def permanently_delete(page: Page) -> None:
        page.delete()


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


class RevisionRepository:
    """Per-language history snapshots for posts and pages (read + lookup)."""

    @staticmethod
    def list_for_post(post: Post) -> QuerySet:
        return post.revisions.select_related("author")

    @staticmethod
    def get_post_revision(post: Post, pk: int):
        return get_object_or_404(post.revisions, pk=pk)

    @staticmethod
    def list_for_page(page: Page) -> QuerySet:
        return page.revisions.select_related("author")

    @staticmethod
    def get_page_revision(page: Page, pk: int):
        return get_object_or_404(page.revisions, pk=pk)


class LikeRepository:
    @staticmethod
    def toggle(post: Post, user) -> bool:
        """Add or remove ``user``'s like on ``post``; return True if now liked.

        Deleting the row is an unlike, so the relation doubles as a toggle and the
        unique constraint is never violated.
        """
        existing = Like.objects.filter(post=post, user=user).first()
        if existing is not None:
            existing.delete()
            return False
        Like.objects.create(post=post, user=user)
        return True

    @staticmethod
    def count_for(post: Post) -> int:
        return post.likes.count()

    @staticmethod
    def is_liked_by(post: Post, user) -> bool:
        if not getattr(user, "is_authenticated", False):
            return False
        return Like.objects.filter(post=post, user=user).exists()
