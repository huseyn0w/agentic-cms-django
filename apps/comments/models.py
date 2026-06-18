from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class CommentStatus(models.TextChoices):
    PENDING = "pending", _("Pending")
    APPROVED = "approved", _("Approved")
    SPAM = "spam", _("Spam")


class CommentQuerySet(models.QuerySet):
    def approved(self) -> models.QuerySet:
        return self.filter(status=CommentStatus.APPROVED)

    def pending(self) -> models.QuerySet:
        return self.filter(status=CommentStatus.PENDING)


class Comment(models.Model):
    """A threaded, moderated comment on a post.

    Bodies are plain text and are ALWAYS rendered autoescaped (never ``|safe``),
    so no HTML sanitisation is needed — markup is shown as literal text. New
    comments default to ``pending`` and are only shown publicly once approved.
    """

    post = models.ForeignKey(
        "content.Post",
        verbose_name=_("post"),
        on_delete=models.CASCADE,
        related_name="comments",
    )
    parent = models.ForeignKey(
        "self",
        verbose_name=_("in reply to"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
    )
    # Set for authenticated commenters; name/email cover guests.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("user"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comments",
    )
    name = models.CharField(_("name"), max_length=80)
    email = models.EmailField(_("email"), blank=True)
    body = models.TextField(_("comment"))
    status = models.CharField(
        _("status"), max_length=10, choices=CommentStatus.choices, default=CommentStatus.PENDING
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    objects = CommentQuerySet.as_manager()

    class Meta:
        verbose_name = _("comment")
        verbose_name_plural = _("comments")
        ordering = ["created_at"]
        permissions = [("moderate_comment", "Can moderate comments")]

    def __str__(self) -> str:
        return f"{self.name} on {self.post_id}"

    @property
    def is_approved(self) -> bool:
        return self.status == CommentStatus.APPROVED

    def approved_replies(self) -> models.QuerySet:
        return self.replies.approved().select_related("user")
