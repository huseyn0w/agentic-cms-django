"""Comment domain events + observers (DESIGN_SYSTEM/architecture: side effects via
signals, never inline in a service).

``comment_created`` is emitted by ``apps.comments.services.submit_comment`` after a
comment is persisted. Receivers (observers) perform the side effects — here, an
email notification to the post author. The service uses ``send_robust`` so a failing
observer can never break comment submission.
"""

from __future__ import annotations

import logging

from django.core.mail import send_mail
from django.dispatch import Signal, receiver
from django.urls import reverse

logger = logging.getLogger(__name__)

# Domain event: a new comment was created. providing_args (informal): comment.
comment_created = Signal()


@receiver(comment_created, dispatch_uid="comments.notify_post_author")
def notify_post_author(sender, comment, **kwargs) -> None:
    """Email the post's author that their post received a comment (pending review)."""
    author = comment.post.author
    recipient = getattr(author, "email", "") if author else ""
    if not recipient:
        return

    post_title = str(comment.post)
    try:
        moderate_url = reverse("dashboard:comment_list")
    except Exception:  # pragma: no cover - reverse failure is non-fatal
        moderate_url = "/dashboard/comments/"

    subject = f"New comment on “{post_title}”"
    body = (
        f"{comment.name} commented on your post “{post_title}”:\n\n"
        f"{comment.body}\n\n"
        f"It is awaiting moderation: {moderate_url}\n"
    )
    # fail_silently: a mail backend hiccup must never affect the visitor's request.
    send_mail(subject, body, None, [recipient], fail_silently=True)
