from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


# django-manager-missing: the reverse `services` relation resolves through a
# parler manager django-stubs can't introspect (django-parler ships no stubs).
class User(AbstractUser):  # type: ignore[django-manager-missing]
    """
    AgenticCms-Django user.

    Extends Django's ``AbstractUser`` (so username/email/password and the full
    auth/permission machinery come for free) with a small author profile.

    Cross-cutting "capabilities" that don't belong to a single model's CRUD —
    e.g. reaching the admin dashboard or managing users/settings — are declared
    as custom permissions below. Per-model permissions (add/change/delete/view
    posts, pages, media, ...) are created automatically as those models land in
    later phases and are assigned to roles by the role sync.
    """

    avatar = models.ImageField(_("avatar"), upload_to="avatars/", blank=True, null=True)
    bio = models.TextField(_("bio"), blank=True)
    website = models.URLField(_("website"), blank=True)

    class Meta(AbstractUser.Meta):  # type: ignore[name-defined]  # django-stubs gap
        permissions = [
            ("access_admin", "Can access the admin dashboard"),
            ("manage_users", "Can manage users and roles"),
            ("manage_settings", "Can manage site settings"),
        ]

    def __str__(self) -> str:
        return self.get_username()

    @property
    def display_name(self) -> str:
        """Best human-readable name: full name if set, else username."""
        return self.get_full_name() or self.get_username()

    def get_absolute_url(self) -> str:
        """Public author archive page."""
        return reverse("accounts:author_detail", args=[self.pk])

    def has_role(self, role_name: str) -> bool:
        """True if the user belongs to the group (role) with this name."""
        return self.groups.filter(name=role_name).exists()

    @property
    def role_names(self) -> list[str]:
        return list(self.groups.values_list("name", flat=True))
