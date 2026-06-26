"""Core data-access layer (repository).

Wraps access to the ``SiteSettings`` singleton so services never touch the model
(and its cached ``load()``) directly.
"""

from __future__ import annotations

from .models import SiteSettings


class SiteSettingsRepository:
    @staticmethod
    def get() -> SiteSettings:
        """The cached site-settings singleton (created on first access)."""
        return SiteSettings.load()
