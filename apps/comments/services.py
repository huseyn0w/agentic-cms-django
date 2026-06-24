"""Comment submission and moderation services.

The single home for comment business logic, reused by the public submission view
and (later) the REST/MCP surface. Follows the house service style used by
``apps.search.services``: plain functions, typed params, plain return values; no
HTTP request/response objects leak in. Views only map the returned outcome to an
HTTP response — they hold no comment domain rules themselves.
"""

from __future__ import annotations

from apps.core.repositories import SiteSettingsRepository

from .forms import CommentForm
from .models import Comment
from .repositories import CommentRepository

# Submission outcomes returned by ``submit_comment`` (mapped to HTTP by the view).
CREATED = "created"
INVALID = "invalid"
DISABLED = "disabled"
LOGIN_REQUIRED = "login_required"

# action -> success message for moderation. "delete" handled in moderate().
_MODERATION_MESSAGES = {
    "approve": "Comment approved.",
    "spam": "Comment marked as spam.",
    "delete": "Comment deleted.",
}


def submit_comment(post, user, data) -> tuple[str, CommentForm | None]:
    """Apply comment policy, then build/validate/persist a comment on ``post``.

    Owns every domain decision so the view stays a pure HTTP boundary. Returns
    ``(outcome, form)``:

    - ``DISABLED`` — comments are turned off site-wide (view → 404). ``form`` None.
    - ``LOGIN_REQUIRED`` — login required and the user is anonymous (view → login).
    - ``CREATED`` — saved pending moderation; ``form`` is the bound, saved form.
    - ``INVALID`` — validation failed; ``form`` carries errors for re-render.

    Authenticated users' identity (user/name/email) comes from their account;
    guests supply name/email via the form.
    """
    site = SiteSettingsRepository.get()
    if not site.allow_comments:
        return DISABLED, None
    if site.comments_require_login and not user.is_authenticated:
        return LOGIN_REQUIRED, None

    comment = Comment(post=post)
    if user.is_authenticated:
        comment.user = user
        comment.name = user.display_name
        comment.email = user.email or ""
    form = CommentForm(data, instance=comment, user=user)
    if form.is_valid():
        CommentRepository.save_from_form(form)
        return CREATED, form
    return INVALID, form


def moderate(comment: Comment, action: str) -> str:
    """Apply a moderation ``action`` to ``comment`` and return a success message.

    Supported actions: ``approve``, ``spam``, ``delete``. Raises ``ValueError`` for
    any other action so callers can map it to a 404/400.
    """
    if action == "approve":
        comment.approve()
    elif action == "spam":
        comment.mark_spam()
    elif action == "delete":
        CommentRepository.delete(comment)
    else:
        raise ValueError(f"Unknown moderation action: {action!r}")
    return _MODERATION_MESSAGES[action]
