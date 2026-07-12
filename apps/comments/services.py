"""Comment submission and moderation services.

The single home for comment business logic, reused by the public submission view
and (later) the REST/MCP surface. Follows the house service style used by
``apps.search.services``: plain functions, typed params, plain return values; no
HTTP request/response objects leak in. Views only map the returned outcome to an
HTTP response — they hold no comment domain rules themselves.
"""

from __future__ import annotations

from django.core.cache import cache
from django.utils.translation import gettext_lazy as _

from apps.core.repositories import SiteSettingsRepository

from .forms import CommentForm
from .models import Comment
from .repositories import CommentRepository
from .signals import comment_created

# Submission outcomes returned by ``submit_comment`` (mapped to HTTP by the view).
CREATED = "created"
INVALID = "invalid"
DISABLED = "disabled"
LOGIN_REQUIRED = "login_required"
RATE_LIMITED = "rate_limited"

# Per-IP comment-submit throttle. Canon is 8 submissions per 60s window, copied
# from agentic-cms-ts's `@Throttle({ default: { limit: 8, ttl: 60_000 } })`. Backed by
# Django's cache (the same mechanism allauth's ACCOUNT_RATE_LIMITS use); accurate
# per-IP limits under multiple workers need a shared backend (Redis) — same caveat
# as the auth limits, landing with the infra phase.
COMMENT_RATE_LIMIT = 8
COMMENT_RATE_WINDOW = 60  # seconds


def client_ip(request) -> str:
    """The real client IP: first ``X-Forwarded-For`` hop, else ``REMOTE_ADDR``.

    Behind a reverse proxy the socket peer is the proxy, so the throttle keys off
    the left-most forwarded address (the original client) — mirroring ts trusting
    the first proxy hop for ``req.ip``.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or "unknown"


def is_rate_limited(request) -> bool:
    """True once this client IP has spent its comment-submit budget for the window.

    Counts one submission attempt per call; the window is a fixed bucket keyed by
    IP so it expires ``COMMENT_RATE_WINDOW`` seconds after the first hit. Fails
    open if the cache is unavailable (never blocks a genuine commenter on infra
    hiccups).
    """
    key = f"comment-submit:{client_ip(request)}"
    # add() only sets when the key is absent, so the first hit starts the window
    # with the correct TTL; later hits just increment. If the bucket expired
    # between add() and incr() (a race), incr() raises ValueError → treat as a
    # fresh window (count 1), never a hard error for a genuine commenter.
    cache.add(key, 0, COMMENT_RATE_WINDOW)
    try:
        count = cache.incr(key)
    except ValueError:
        count = 1
    return count > COMMENT_RATE_LIMIT


# action -> success message for moderation. "delete" handled in moderate().
_MODERATION_MESSAGES = {
    "approve": _("Comment approved."),
    "spam": _("Comment marked as spam."),
    "delete": _("Comment deleted."),
}


def submit_comment(post, user, data, request=None) -> tuple[str, CommentForm | None]:
    """Apply comment policy, then build/validate/persist a comment on ``post``.

    Owns every domain decision so the view stays a pure HTTP boundary. Returns
    ``(outcome, form)``:

    - ``DISABLED`` — comments are turned off site-wide (view → 404). ``form`` None.
    - ``LOGIN_REQUIRED`` — login required and the user is anonymous (view → login).
    - ``RATE_LIMITED`` — this client IP exceeded the per-minute submit budget
      (view → 429). ``form`` None.
    - ``CREATED`` — saved pending moderation; ``form`` is the bound, saved form.
    - ``INVALID`` — validation failed; ``form`` carries errors for re-render.

    Authenticated users' identity (user/name/email) comes from their account;
    guests supply name/email via the form. ``request`` (when supplied) is used only
    to derive the client IP for the throttle — no other HTTP state leaks in.
    """
    site = SiteSettingsRepository.get()
    if not site.allow_comments:
        return DISABLED, None
    if site.comments_require_login and not user.is_authenticated:
        return LOGIN_REQUIRED, None
    # Per-IP throttle: count the attempt only once we know the submission is
    # otherwise allowed (comments on, login satisfied), so disabled/redirect
    # responses don't burn a genuine commenter's budget.
    if request is not None and is_rate_limited(request):
        return RATE_LIMITED, None

    comment = Comment(post=post)
    if user.is_authenticated:
        comment.user = user
        comment.name = user.display_name
        comment.email = user.email or ""
    form = CommentForm(data, instance=comment, user=user)
    if form.is_valid():
        saved = CommentRepository.save_from_form(form)
        # Side effects run in observers, never inline here. send_robust so a failing
        # receiver (e.g. mail outage) can't break the submission.
        comment_created.send_robust(sender=Comment, comment=saved)
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
