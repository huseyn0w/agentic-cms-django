"""MCP tool registry — management operations exposed to an AI client.

Each tool declares the permission(s) it needs; the executor re-verifies them
server-side against the calling user before running (no second source of truth).
Handlers delegate to the existing app services/repositories, so the tools share
exactly the same rules (owner-scoping, publish-gating, sanitisation) as the UI.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from apps.accounts.repositories import UserRepository
from apps.comments import services as comment_services
from apps.comments.repositories import CommentRepository
from apps.content import services as content_services
from apps.content.repositories import (
    CategoryRepository,
    PageRepository,
    PostRepository,
    TagRepository,
)
from apps.core.repositories import SiteSettingsRepository
from apps.media.repositories import MediaRepository


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    permissions: tuple[str, ...]
    handler: Callable
    input_schema: dict = field(default_factory=dict)
    # State-mutating tools require the OAuth ``write`` scope (in addition to the
    # per-tool model permission). Read-only tools (list/get/settings.get) do not.
    write: bool = False

    def schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {"type": "object", "properties": self.input_schema},
        }


# --- representation helpers (plain dicts; translations via any_language) --- #
def _post_dict(post, full: bool = False) -> dict:
    data = {
        "id": post.pk,
        "slug": post.slug,
        "title": post.safe_translation_getter("title", any_language=True),
        "status": post.status,
    }
    if full:
        data["body"] = post.safe_translation_getter("body", any_language=True, default="")
    return data


def _taxonomy_dict(obj) -> dict:
    return {
        "id": obj.pk,
        "slug": obj.slug,
        "name": obj.safe_translation_getter("name", any_language=True),
    }


# --- handlers (user, arguments) -> JSON-serialisable result --- #
def _list_posts(user, args) -> dict:
    posts = PostRepository.for_dashboard(user)[:50]
    return {"posts": [_post_dict(p) for p in posts]}


def _get_post(user, args) -> dict:
    return _post_dict(PostRepository.get_editable(user, args["id"]), full=True)


def _create_post(user, args) -> dict:
    return _post_dict(content_services.api_create_post(args, user), full=True)


def _update_post(user, args) -> dict:
    post = PostRepository.get_editable(user, args["id"])
    return _post_dict(content_services.api_update_post(post, args, user), full=True)


def _publish_post(user, args) -> dict:
    post = PostRepository.get_editable(user, args["id"])
    return _post_dict(content_services.api_update_post(post, {"status": "published"}, user))


def _delete_post(user, args) -> dict:
    post = PostRepository.get_editable(user, args["id"])
    post.trash()
    return {"id": post.pk, "trashed": True}


def _list_pages(user, args) -> dict:
    pages = PageRepository.all_for_admin()[:50]
    return {
        "pages": [
            {
                "id": p.pk,
                "slug": p.slug,
                "title": p.safe_translation_getter("title", any_language=True),
                "status": p.status,
            }
            for p in pages
        ]
    }


def _list_categories(user, args) -> dict:
    return {"categories": [_taxonomy_dict(c) for c in CategoryRepository.with_post_counts()]}


def _list_tags(user, args) -> dict:
    return {"tags": [_taxonomy_dict(t) for t in TagRepository.with_post_counts()]}


def _moderate_comment(user, args) -> dict:
    comment = CommentRepository.get(args["id"])
    message = comment_services.moderate(comment, args["action"])
    return {"id": comment.pk, "status": comment.status, "message": message}


def _list_media(user, args) -> dict:
    assets = MediaRepository.all()[:50]
    return {
        "media": [
            {"id": a.pk, "title": str(a), "url": a.file.url, "mime_type": a.mime_type}
            for a in assets
        ]
    }


def _list_users(user, args) -> dict:
    users = UserRepository.all_with_groups()
    return {
        "users": [
            {
                "id": u.pk,
                "username": u.get_username(),
                "name": u.display_name,
                "roles": u.role_names,
            }
            for u in users
        ]
    }


def _get_settings(user, args) -> dict:
    settings = SiteSettingsRepository.get()
    return {
        "site_name": settings.site_name,
        "tagline": settings.tagline,
        "allow_comments": settings.allow_comments,
    }


TOOLS: list[Tool] = [
    Tool("posts.list", "List posts you may manage.", ("content.view_post",), _list_posts),
    Tool(
        "posts.get",
        "Get one post by id.",
        ("content.view_post",),
        _get_post,
        {"id": {"type": "integer"}},
    ),
    Tool(
        "posts.create",
        "Create a post.",
        ("content.add_post",),
        _create_post,
        {"title": {"type": "string"}, "body": {"type": "string"}, "status": {"type": "string"}},
        write=True,
    ),
    Tool(
        "posts.update",
        "Update a post.",
        ("content.change_post",),
        _update_post,
        {"id": {"type": "integer"}, "title": {"type": "string"}, "body": {"type": "string"}},
        write=True,
    ),
    Tool(
        "posts.publish",
        "Publish a post.",
        ("content.publish_post",),
        _publish_post,
        {"id": {"type": "integer"}},
        write=True,
    ),
    Tool(
        "posts.delete",
        "Move a post to trash.",
        ("content.delete_post",),
        _delete_post,
        {"id": {"type": "integer"}},
        write=True,
    ),
    Tool("pages.list", "List pages.", ("content.view_page",), _list_pages),
    Tool("categories.list", "List categories.", ("content.view_category",), _list_categories),
    Tool("tags.list", "List tags.", ("content.view_tag",), _list_tags),
    Tool(
        "comments.moderate",
        "Approve/spam/delete a comment.",
        ("comments.moderate_comment",),
        _moderate_comment,
        {"id": {"type": "integer"}, "action": {"type": "string"}},
        write=True,
    ),
    Tool("media.list", "List media assets.", ("media.view_mediaasset",), _list_media),
    Tool("users.list", "List users and roles.", ("accounts.manage_users",), _list_users),
    Tool("settings.get", "Read site settings.", ("accounts.manage_settings",), _get_settings),
]

TOOLS_BY_NAME: dict[str, Tool] = {tool.name: tool for tool in TOOLS}
