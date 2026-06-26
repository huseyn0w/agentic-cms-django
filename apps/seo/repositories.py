"""SEO data-access layer (repository).

Wraps access to the ``SeoSettings`` singleton so services never touch the model
(and its cached ``load()``) directly.
"""

from __future__ import annotations

from .models import SeoSettings


class SeoSettingsRepository:
    @staticmethod
    def get() -> SeoSettings:
        """The cached SEO-settings singleton (created on first access)."""
        return SeoSettings.load()
