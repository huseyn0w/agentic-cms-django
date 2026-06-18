from __future__ import annotations

from django.core.cache import cache
from django.db import models
from django.utils.html import strip_tags
from django.utils.text import Truncator
from django.utils.translation import gettext_lazy as _

_CACHE_KEY = "seo_settings"

# Keep meta descriptions in the range search engines actually display.
META_DESCRIPTION_MAX = 160


class SeoSettings(models.Model):
    """Site-wide SEO/GEO configuration, stored as a single row (singleton).

    Mirrors the SiteSettings pattern (cached, pk=1). Exposed to every template as
    ``seo`` via apps.seo.context_processors.seo_settings.
    """

    # Open Graph / social defaults
    og_site_name = models.CharField(
        _("Open Graph site name"),
        max_length=100,
        blank=True,
        help_text=_("Defaults to the site name when blank."),
    )
    default_og_image = models.ImageField(
        _("default share image"),
        upload_to="seo/",
        blank=True,
        null=True,
        help_text=_("Used for Open Graph/Twitter when a page has no image of its own."),
    )
    default_meta_description = models.CharField(
        _("default meta description"),
        max_length=200,
        blank=True,
        help_text=_("Fallback description for pages that don't set their own."),
    )
    twitter_handle = models.CharField(
        _("Twitter handle"),
        max_length=40,
        blank=True,
        help_text=_("e.g. @yourbrand — used for twitter:site."),
    )

    # Analytics / verification
    google_analytics_id = models.CharField(
        _("Google Analytics ID"), max_length=20, blank=True, help_text=_("e.g. G-XXXXXXXXXX")
    )
    google_tag_manager_id = models.CharField(
        _("Google Tag Manager ID"), max_length=20, blank=True, help_text=_("e.g. GTM-XXXXXXX")
    )
    google_site_verification = models.CharField(
        _("Google site verification"), max_length=100, blank=True
    )
    bing_site_verification = models.CharField(
        _("Bing site verification"), max_length=100, blank=True
    )

    # Indexing
    discourage_search = models.BooleanField(
        _("discourage search engines"),
        default=False,
        help_text=_("Adds a site-wide noindex,nofollow. Use for staging sites only."),
    )

    class Meta:
        verbose_name = _("SEO settings")
        verbose_name_plural = _("SEO settings")

    def __str__(self) -> str:
        return "SEO settings"

    def save(self, *args, **kwargs) -> None:
        self.pk = 1  # enforce a single row
        super().save(*args, **kwargs)
        cache.delete(_CACHE_KEY)

    @classmethod
    def load(cls) -> SeoSettings:
        """Return the singleton, cached, creating it on first access."""
        settings_obj = cache.get(_CACHE_KEY)
        if settings_obj is None:
            settings_obj, _created = cls.objects.get_or_create(pk=1)
            cache.set(_CACHE_KEY, settings_obj)
        return settings_obj


class SeoFieldsMixin:
    """Per-content SEO helpers, shared by Post/Page (and later Service).

    The concrete model supplies the fields (``meta_title``, ``meta_description``,
    ``canonical_url``, ``noindex``, ``og_image``) plus ``title``; this mixin turns
    them into the values the <head> needs, with sensible fallbacks. It is plain
    Python (no DB fields) so it composes with parler's TranslatableModel.
    """

    def seo_title(self) -> str:
        return (getattr(self, "meta_title", "") or "").strip() or self.title

    def seo_description(self) -> str:
        explicit = (getattr(self, "meta_description", "") or "").strip()
        if explicit:
            return explicit
        # Derive from excerpt, then body, stripped of HTML and truncated.
        source = getattr(self, "excerpt", "") or getattr(self, "body", "") or ""
        text = strip_tags(source).strip()
        return Truncator(text).chars(META_DESCRIPTION_MAX) if text else ""

    def seo_is_noindex(self, seo_settings: SeoSettings | None = None) -> bool:
        if getattr(self, "noindex", False):
            return True
        if seo_settings is not None:
            return seo_settings.discourage_search
        return False

    def seo_robots(self, seo_settings: SeoSettings | None = None) -> str:
        return "noindex,nofollow" if self.seo_is_noindex(seo_settings) else "index,follow"

    def og_image_url(self) -> str:
        image = getattr(self, "og_image", None)
        if image:
            return image.url
        return ""
