from __future__ import annotations

from collections.abc import Sequence

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin


class AdminAccessMixin(LoginRequiredMixin, PermissionRequiredMixin):
    """Base gate for every admin-panel view.

    Unauthenticated users are redirected to login; authenticated users without
    `accounts.access_admin` get a 403. Individual views add their own, more
    specific permission via `permission_required` (a tuple is ANDed).
    """

    # Subclasses override this with a tuple of permissions (ANDed by Django), so
    # the declared type must admit both a single permission and a sequence.
    permission_required: str | Sequence[str] = "accounts.access_admin"
