"""Account data-access layer (repository).

The single home for User ORM access used by the dashboard user-management service.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

User = get_user_model()


class UserRepository:
    @staticmethod
    def all_with_groups() -> QuerySet:
        """All users for the admin list, with their role groups prefetched."""
        return User.objects.prefetch_related("groups").order_by("username")

    @staticmethod
    def get(pk: int):
        return get_object_or_404(User, pk=pk)

    @staticmethod
    def get_by_username(username: str):
        """The user with ``username`` or None (used by the token-issuing command)."""
        return User.objects.filter(username=username).first()

    @staticmethod
    def count_all() -> int:
        return User.objects.count()
