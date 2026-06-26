"""Comment data-access layer (repository).

The single home for comment ORM access used by the comment services. Status
transitions stay as model methods (``Comment.approve()/mark_spam()`` — the
entity's own behavior); this repository owns queries, form persistence and delete.
"""

from __future__ import annotations

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

from .forms import CommentForm
from .models import Comment


class CommentRepository:
    @staticmethod
    def approved_top_level(post) -> QuerySet:
        """Approved, non-reply comments on ``post`` (replies render under parents)."""
        return post.comments.approved().filter(parent__isnull=True).select_related("user")

    @staticmethod
    def save_from_form(form: CommentForm) -> Comment:
        """Persist a validated CommentForm and return the comment."""
        return form.save()

    @staticmethod
    def get(pk: int) -> Comment:
        return get_object_or_404(Comment, pk=pk)

    @staticmethod
    def delete(comment: Comment) -> None:
        comment.delete()

    # -- Dashboard moderation queries -- #
    @staticmethod
    def for_moderation(status: str | None = None) -> QuerySet:
        """All comments for the moderation list, newest first, optional status filter.

        ``status`` is assumed pre-validated by the service.
        """
        qs = Comment.objects.select_related("post", "user").order_by("-created_at")
        if status:
            qs = qs.filter(status=status)
        return qs

    @staticmethod
    def pending_count() -> int:
        return Comment.objects.pending().count()
