"""Account services — public author archive orchestration.

Views stay at the HTTP boundary; data access goes through repositories
(``apps.accounts.repositories``, ``apps.content.repositories``). Raising ``Http404``
is a not-found signal the view re-raises.
"""

from __future__ import annotations

from django.db.models import QuerySet
from django.http import Http404

from apps.content.repositories import PostRepository

from .repositories import UserRepository


def get_author_for_view(pk: int):
    """A user who has at least one published post, else Http404.

    Gating on published authorship keeps non-author accounts (subscribers, staff
    with no posts) un-enumerable via ``/authors/<id>/``.
    """
    author = UserRepository.get(pk)
    if not PostRepository.published_by_author(author).exists():
        raise Http404
    return author


def author_posts(author) -> QuerySet:
    """An author's published posts for their public archive."""
    return PostRepository.published_by_author(author)
