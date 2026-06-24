"""Dashboard service functions.

Orchestration for the admin dashboard. Holds no ORM itself — all data access goes
through the per-app repositories; singleton/registry access (settings, themes,
plugins) is funnelled here so the views never import those modules directly.
Follows the house service style used by ``apps.search.services``.
"""

from __future__ import annotations

import difflib

from apps.accounts.repositories import UserRepository
from apps.comments.models import CommentStatus
from apps.comments.repositories import CommentRepository
from apps.comments.services import moderate as _moderate
from apps.content.models import Status
from apps.content.repositories import (
    CategoryRepository,
    PageRepository,
    PostRepository,
    RevisionRepository,
    ServiceRepository,
    TagRepository,
)
from apps.core.repositories import SiteSettingsRepository
from apps.media.repositories import MediaRepository
from apps.plugins import registry as plugins
from apps.seo.repositories import SeoSettingsRepository
from apps.themes import registry as themes


# --------------------------------------------------------------------------- #
# Home
# --------------------------------------------------------------------------- #
def dashboard_stats() -> dict[str, int]:
    """Top-line counts shown on the dashboard home (posts, pages, media, users)."""
    return {
        "posts": PostRepository.count_all(),
        "pages": PageRepository.count_all(),
        "media": MediaRepository.count_all(),
        "users": UserRepository.count_all(),
    }


def recent_posts(user, limit: int = 6):
    """Recent posts the user may edit (owner-scoped for non-managers)."""
    return PostRepository.recent_editable(user, limit)


# --------------------------------------------------------------------------- #
# Posts
# --------------------------------------------------------------------------- #
def list_posts(user, status: str | None = None, search: str | None = None):
    """Owner-scoped post list with validated status/search filters applied."""
    valid_status = status if status in Status.values else None
    return PostRepository.for_dashboard(user, status=valid_status, search=(search or None))


def editable_posts(user):
    """Owner-scoped post queryset (used by scope mixin / delete)."""
    return PostRepository.for_dashboard(user)


def prepare_new_post(post, user) -> None:
    """Stamp authorship on a new post before the form persists it."""
    post.author = user


# -- Trash / restore / permanent-delete (owner-scoped for non-managers) -- #
def list_trashed_posts(user):
    return PostRepository.trashed_for_dashboard(user)


def trash_post(user, pk: int) -> None:
    """Soft-delete a post the user may manage (Http404 otherwise)."""
    PostRepository.get_editable(user, pk).trash()


def restore_post(user, pk: int) -> None:
    PostRepository.get_trashed_editable(user, pk).restore()


def permanently_delete_post(user, pk: int) -> None:
    PostRepository.permanently_delete(PostRepository.get_trashed_editable(user, pk))


# -- Revisions (history + diff + restore) -- #
def _text_diff(old: str, new: str) -> list[dict[str, str]]:
    """A line-level diff of two bodies as ``{kind, text}`` rows for the template.

    ``kind`` is one of equal/add/remove (``+`` = present only in the current copy,
    ``-`` = present only in the revision being viewed). Differ's ``?`` hint lines
    are dropped.
    """
    rows: list[dict[str, str]] = []
    for line in difflib.Differ().compare(old.splitlines(), new.splitlines()):
        marker, text = line[:2], line[2:]
        if marker == "+ ":
            rows.append({"kind": "add", "text": text})
        elif marker == "- ":
            rows.append({"kind": "remove", "text": text})
        elif marker == "? ":
            continue
        else:
            rows.append({"kind": "equal", "text": text})
    return rows


def _revision_diff(obj, revision) -> dict:
    """Diff a stored revision against the object's current content (its language)."""
    code = revision.language_code
    current_title = obj.safe_translation_getter("title", default="", language_code=code)
    current_body = obj.safe_translation_getter("body", default="", language_code=code)
    return {
        "language_code": code,
        "title_old": revision.title,
        "title_new": current_title,
        "title_changed": revision.title != current_title,
        "body": _text_diff(revision.body, current_body),
    }


def post_revisions_context(user, post_pk: int, revision_pk: str | None = None) -> dict:
    """History list (+ optional selected-revision diff) for a post the user edits."""
    post = PostRepository.get_editable(user, post_pk)
    ctx: dict = {
        "obj": post,
        "revisions": RevisionRepository.list_for_post(post),
        "selected": None,
        "diff": None,
        "restore_url_name": "dashboard:post_revision_restore",
        "back_url_name": "dashboard:post_edit",
    }
    if revision_pk:
        selected = RevisionRepository.get_post_revision(post, revision_pk)
        ctx["selected"] = selected
        ctx["diff"] = _revision_diff(post, selected)
    return ctx


def restore_post_revision(user, post_pk: int, revision_pk: int) -> None:
    post = PostRepository.get_editable(user, post_pk)
    post.restore_revision(RevisionRepository.get_post_revision(post, revision_pk))


# --------------------------------------------------------------------------- #
# Pages / Services
# --------------------------------------------------------------------------- #
def list_pages():
    return PageRepository.all_for_admin()


def list_trashed_pages():
    return PageRepository.trashed_for_admin()


def trash_page(pk: int) -> None:
    PageRepository.get_for_admin(pk).trash()


def restore_page(pk: int) -> None:
    PageRepository.get_trashed(pk).restore()


def permanently_delete_page(pk: int) -> None:
    PageRepository.permanently_delete(PageRepository.get_trashed(pk))


def page_revisions_context(pk: int, revision_pk: str | None = None) -> dict:
    page = PageRepository.get_for_admin(pk)
    ctx: dict = {
        "obj": page,
        "revisions": RevisionRepository.list_for_page(page),
        "selected": None,
        "diff": None,
        "restore_url_name": "dashboard:page_revision_restore",
        "back_url_name": "dashboard:page_edit",
    }
    if revision_pk:
        selected = RevisionRepository.get_page_revision(page, revision_pk)
        ctx["selected"] = selected
        ctx["diff"] = _revision_diff(page, selected)
    return ctx


def restore_page_revision(pk: int, revision_pk: int) -> None:
    page = PageRepository.get_for_admin(pk)
    page.restore_revision(RevisionRepository.get_page_revision(page, revision_pk))


def list_services():
    return ServiceRepository.all_for_admin()


def prepare_new_page(page, user) -> None:
    page.author = user


def prepare_new_service(service, user) -> None:
    service.author = user


# --------------------------------------------------------------------------- #
# Taxonomy
# --------------------------------------------------------------------------- #
def list_categories():
    return CategoryRepository.with_post_counts()


def list_tags():
    return TagRepository.with_post_counts()


# --------------------------------------------------------------------------- #
# Users
# --------------------------------------------------------------------------- #
def list_users():
    return UserRepository.all_with_groups()


def get_user(pk: int):
    return UserRepository.get(pk)


# --------------------------------------------------------------------------- #
# Comments
# --------------------------------------------------------------------------- #
def list_comments(status: str | None = None):
    """Moderation list with a validated status filter applied."""
    valid_status = status if status in CommentStatus.values else None
    return CommentRepository.for_moderation(valid_status)


def pending_comment_count() -> int:
    return CommentRepository.pending_count()


def comment_status_choices():
    return CommentStatus.choices


def get_comment(pk: int):
    return CommentRepository.get(pk)


def moderate_comment(comment, action: str) -> str:
    """Apply a moderation action; raises ValueError on an unknown action."""
    return _moderate(comment, action)


# --------------------------------------------------------------------------- #
# Settings singletons
# --------------------------------------------------------------------------- #
def load_site_settings():
    return SiteSettingsRepository.get()


def load_seo_settings():
    return SeoSettingsRepository.get()


# --------------------------------------------------------------------------- #
# Appearance / Plugins (registry-backed)
# --------------------------------------------------------------------------- #
def available_themes():
    return themes.get_available_themes()


def active_theme_slug():
    return themes.get_active_theme_slug()


def activate_theme(slug: str) -> bool:
    return themes.activate_theme(slug)


def installed_plugins_with_state() -> list[dict]:
    return [
        {"info": info, "enabled": plugins.is_plugin_enabled(info.slug)}
        for info in plugins.get_installed_plugins()
    ]


def is_plugin_enabled(slug: str) -> bool:
    return plugins.is_plugin_enabled(slug)


def set_plugin_enabled(slug: str, enabled: bool) -> bool:
    return plugins.set_enabled(slug, enabled)
