"""Public content services — orchestration for the content views.

Views stay at the HTTP boundary; these services hold the visibility rules and
context assembly and delegate ALL data access to repositories
(``apps.content.repositories``, ``apps.comments.repositories``). No ``Model.objects``
here. Raising ``Http404`` is a not-found signal the view re-raises.
"""

from __future__ import annotations

from django.db.models import QuerySet
from django.http import Http404

from apps.comments.forms import CommentForm
from apps.comments.repositories import CommentRepository
from apps.core.repositories import SiteSettingsRepository

from .models import Category, Page, Post, Service, Tag
from .repositories import (
    CategoryRepository,
    LikeRepository,
    PageRepository,
    PostRepository,
    ServiceRepository,
    TagRepository,
)


def list_published_posts() -> QuerySet:
    """Published posts for public lists, with author + taxonomy prefetched."""
    return PostRepository.published()


def get_category(slug: str) -> Category:
    """The category with ``slug`` or raise Http404."""
    return CategoryRepository.get_by_slug(slug)


def get_tag(slug: str) -> Tag:
    """The tag with ``slug`` or raise Http404."""
    return TagRepository.get_by_slug(slug)


def posts_in_category(category: Category) -> QuerySet:
    """Published posts filed under ``category``."""
    return PostRepository.published_in_category(category)


def posts_with_tag(tag: Tag) -> QuerySet:
    """Published posts carrying ``tag``."""
    return PostRepository.published_with_tag(tag)


def get_post_for_view(slug: str, user) -> Post:
    """Fetch a post by slug, enforcing object-level visibility (Http404 if hidden)."""
    post = PostRepository.get_by_slug(slug)
    if not post.can_be_viewed_by(user):
        raise Http404
    return post


def get_page_for_view(slug: str, user) -> Page:
    """Fetch a page by slug, enforcing object-level visibility (Http404 if hidden)."""
    page = PageRepository.get_by_slug(slug)
    if not page.can_be_viewed_by(user):
        raise Http404
    return page


def list_published_services() -> QuerySet:
    """Published services for the public services index."""
    return ServiceRepository.published()


def get_service_for_view(slug: str, user) -> Service:
    """Fetch a service by slug, enforcing object-level visibility (Http404 if hidden)."""
    service = ServiceRepository.get_by_slug(slug)
    if not service.can_be_viewed_by(user):
        raise Http404
    return service


def related_posts(post: Post, limit: int = 4) -> QuerySet:
    """Published posts sharing a category/tag with ``post`` (excludes ``post``)."""
    return PostRepository.related_by_taxonomy(post, limit=limit)


def post_detail_context(post: Post, user, comment_form: CommentForm | None = None) -> dict:
    """Comment- and related-post context for a post detail page.

    Returns the comment toggles plus, when comments are enabled, the approved
    top-level comment thread and a form (the caller may inject a bound form to
    re-render validation errors), and a capped "related posts" list by shared
    taxonomy for the detail block.
    """
    site = SiteSettingsRepository.get()
    ctx: dict = {
        "comments_enabled": site.allow_comments,
        "comments_require_login": site.comments_require_login,
        "related_posts": related_posts(post),
    }
    if site.allow_comments:
        ctx["comments"] = CommentRepository.approved_top_level(post)
        ctx["comment_form"] = comment_form or CommentForm(user=user)
    ctx["likes_count"] = LikeRepository.count_for(post)
    ctx["user_has_liked"] = LikeRepository.is_liked_by(post, user)
    return ctx


def toggle_post_like(post: Post, user) -> tuple[bool, int]:
    """Toggle ``user``'s like on ``post``; return (now_liked, total_likes)."""
    liked = LikeRepository.toggle(post, user)
    return liked, LikeRepository.count_for(post)


def get_post_for_action(slug: str) -> Post:
    """Fetch a post by slug for a write action (like), or Http404."""
    return PostRepository.get_by_slug(slug)


_WRITABLE_POST_FIELDS = ("title", "excerpt", "body", "status")


def _apply_post_data(post: Post, data: dict) -> None:
    """Copy validated API data onto a post (translated fields in the active language)."""
    for field in _WRITABLE_POST_FIELDS:
        if field in data:
            setattr(post, field, data[field])
    if data.get("slug"):
        post.slug = data["slug"]


def api_create_post(data: dict, user) -> Post:
    """Create a post from API data, owned by ``user`` and publish-gated."""
    post = PostRepository.new(author=user)
    _apply_post_data(post, data)
    post.gate_publish_state(user)  # non-publishers are forced to draft
    return PostRepository.save(post)


def api_update_post(post: Post, data: dict, user) -> Post:
    """Update a post from API data, preserving publish state for non-publishers."""
    _apply_post_data(post, data)
    post.gate_publish_state(user)
    return PostRepository.save(post)


def publish_scheduled_content() -> dict[str, int]:
    """Publish every draft whose scheduled time has arrived; return per-type counts.

    Each item is flipped via its own ``publish_scheduled`` transition (so no ORM
    lives here); the worker/cron command calls this.
    """
    counts: dict[str, int] = {}
    for label, repo in (
        ("posts", PostRepository),
        ("pages", PageRepository),
        ("services", ServiceRepository),
    ):
        due = list(repo.due_for_publish())
        for item in due:
            item.publish_scheduled()
        counts[label] = len(due)
    return counts
