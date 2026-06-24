from __future__ import annotations

from django.core.cache import cache
from django.db import models
from django.utils.translation import gettext_lazy as _

_CACHE_KEY = "site_settings"


class SiteSettings(models.Model):
    """Site-wide configuration, stored as a single row (singleton)."""

    site_name = models.CharField(_("site name"), max_length=100, default="Cmstack-Django")
    tagline = models.CharField(_("tagline"), max_length=200, blank=True)
    posts_per_page = models.PositiveIntegerField(_("posts per page"), default=10)
    active_theme = models.SlugField(_("active theme"), max_length=50, default="default")
    # Comments (Phase 9)
    allow_comments = models.BooleanField(_("allow comments"), default=True)
    comments_require_login = models.BooleanField(_("require login to comment"), default=False)

    class Meta:
        verbose_name = _("site settings")
        verbose_name_plural = _("site settings")

    def __str__(self) -> str:
        return self.site_name

    def save(self, *args, **kwargs) -> None:
        self.pk = 1  # enforce a single row
        super().save(*args, **kwargs)
        cache.delete(_CACHE_KEY)

    @classmethod
    def load(cls) -> SiteSettings:
        """Return the singleton, cached, creating it on first access."""
        settings_obj = cache.get(_CACHE_KEY)
        if settings_obj is None:
            settings_obj, _created = cls.objects.get_or_create(pk=1)
            cache.set(_CACHE_KEY, settings_obj)
        return settings_obj
