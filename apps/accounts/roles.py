"""
Default roles for AgenticCms-Django.

Roles are plain Django ``Group`` objects; granular access is Django permissions.
Each role lists permission codenames as ``"<app_label>.<codename>"``. The role
sync (see :mod:`apps.accounts.signals`) is idempotent and assigns only the
permissions that currently exist — so this map can name permissions from models
that arrive in later phases (content, media, comments) without breaking now.

Administrator is intentionally NOT a Django superuser: it is granted its powers
explicitly, so the permission system stays the single source of truth.
"""

from __future__ import annotations

# Account-level capabilities (defined on the User model in this phase).
_ADMIN_CAPS = ["accounts.access_admin", "accounts.manage_users", "accounts.manage_settings"]

# Content permissions (apps.content, Phase 3). "publish_post" is a custom perm.
_POST_PERMS = ["add_post", "change_post", "delete_post", "view_post", "publish_post"]
_PAGE_PERMS = ["add_page", "change_page", "delete_page", "view_page"]
_TAXONOMY_PERMS = [
    "add_category",
    "change_category",
    "delete_category",
    "view_category",
    "add_tag",
    "change_tag",
    "delete_tag",
    "view_tag",
]
# Service (GEO) permissions (apps.content, Phase 8.5).
_SERVICE_PERMS = ["add_service", "change_service", "delete_service", "view_service"]
_CONTENT_FULL = (
    [f"content.{p}" for p in _POST_PERMS]
    + [f"content.{p}" for p in _PAGE_PERMS]
    + [f"content.{p}" for p in _SERVICE_PERMS]
    + [f"content.{p}" for p in _TAXONOMY_PERMS]
)

# Media permissions (apps.media, Phase 4).
_MEDIA_FULL = [
    f"media.{p}"
    for p in ("add_mediaasset", "change_mediaasset", "delete_mediaasset", "view_mediaasset")
]
_MEDIA_CONTRIB = ["media.add_mediaasset", "media.view_mediaasset"]

# Comment permissions (apps.comments, Phase 9). "moderate_comment" is custom.
_COMMENT_MODERATION = [
    "comments.view_comment",
    "comments.change_comment",
    "comments.delete_comment",
    "comments.moderate_comment",
]

# Author: create/edit/publish own posts + upload media. Django permissions are
# model-level, so "own" scoping is applied at the object level where it matters —
# e.g. draft preview (Post.can_be_viewed_by); the Phase 5 admin will likewise
# scope edit/list views to ownership for Authors/Contributors.
_AUTHOR_PERMS = [
    "accounts.access_admin",
    "content.add_post",
    "content.change_post",
    "content.view_post",
    "content.publish_post",
    "content.view_category",
    "content.view_tag",
] + _MEDIA_CONTRIB

# Contributor: draft posts, cannot publish or delete, cannot upload media.
_CONTRIBUTOR_PERMS = [
    "accounts.access_admin",
    "content.add_post",
    "content.change_post",
    "content.view_post",
    "content.view_category",
    "content.view_tag",
]

DEFAULT_ROLES: dict[str, list[str]] = {
    "Administrator": _ADMIN_CAPS + _CONTENT_FULL + _MEDIA_FULL + _COMMENT_MODERATION,
    "Editor": ["accounts.access_admin"] + _CONTENT_FULL + _MEDIA_FULL + _COMMENT_MODERATION,
    "Author": _AUTHOR_PERMS,
    "Contributor": _CONTRIBUTOR_PERMS,
    "Subscriber": [],  # authenticated reader; profile only
}

# The role assigned to brand-new self-service signups.
DEFAULT_SIGNUP_ROLE = "Subscriber"
