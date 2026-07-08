from __future__ import annotations

import re
from typing import cast

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils.translation import gettext_lazy as _
from parler.forms import TranslatableModelForm

from apps.content.models import Category, Page, Post, Service, Tag
from apps.core.models import SiteSettings
from apps.menus.models import LinkType, Menu, MenuItem
from apps.menus.repositories import MenuItemRepository
from apps.seo.models import SeoSettings

User = get_user_model()

# The HTML5 datetime-local control emits e.g. "2026-06-25T09:00".
_DATETIME_LOCAL_FORMAT = "%Y-%m-%dT%H:%M"


def _schedule_widget() -> forms.DateTimeInput:
    return forms.DateTimeInput(attrs={"type": "datetime-local"}, format=_DATETIME_LOCAL_FORMAT)


def _accept_datetime_local(field: forms.DateTimeField) -> None:
    """Let a DateTimeField also parse the datetime-local value the widget emits."""
    field.input_formats = [_DATETIME_LOCAL_FORMAT, *field.input_formats]


class PostForm(TranslatableModelForm):
    class Meta:
        model = Post
        fields = [
            "title",
            "slug",
            "excerpt",
            "body",
            "featured_image",
            "status",
            "scheduled_at",
            "categories",
            "tags",
            # SEO (per language for meta_title/description; shared otherwise)
            "meta_title",
            "meta_description",
            "canonical_url",
            "og_image",
            "noindex",
        ]
        widgets = {
            "body": forms.HiddenInput(),  # driven by the Trix editor in the template
            "excerpt": forms.Textarea(attrs={"rows": 3}),
            "meta_description": forms.Textarea(attrs={"rows": 2}),
            "scheduled_at": _schedule_widget(),
        }
        help_texts = {
            "slug": _("Leave blank to generate from the title."),
            "meta_title": _("Overrides the page title in search results (≤70 chars)."),
            "meta_description": _("Shown in search results; falls back to the excerpt."),
        }

    def __init__(self, *args, can_publish: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["body"].required = False
        _accept_datetime_local(self.fields["scheduled_at"])
        if not can_publish:
            # Non-publishers can't change publish state at all, so don't offer the
            # status or scheduling fields; the view preserves the stored status
            # (see PublishGatingMixin).
            del self.fields["status"]
            del self.fields["scheduled_at"]


class PageForm(TranslatableModelForm):
    class Meta:
        model = Page
        fields = [
            "title",
            "slug",
            "body",
            "template",
            "status",
            "scheduled_at",
            "parent",
            "meta_title",
            "meta_description",
            "canonical_url",
            "og_image",
            "noindex",
        ]
        widgets = {
            "body": forms.HiddenInput(),
            "meta_description": forms.Textarea(attrs={"rows": 2}),
            "scheduled_at": _schedule_widget(),
        }
        help_texts = {"slug": _("Leave blank to generate from the title.")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["body"].required = False
        _accept_datetime_local(self.fields["scheduled_at"])


class ServiceForm(TranslatableModelForm):
    class Meta:
        model = Service
        fields = [
            "title",
            "slug",
            "summary",
            "description",
            "price",
            "area_served",
            "faq",
            "status",
            "scheduled_at",
            "meta_title",
            "meta_description",
            "canonical_url",
            "og_image",
            "noindex",
        ]
        widgets = {
            "description": forms.HiddenInput(),  # Trix editor in the template
            "summary": forms.Textarea(attrs={"rows": 2}),
            "faq": forms.Textarea(attrs={"rows": 6}),
            "meta_description": forms.Textarea(attrs={"rows": 2}),
            "scheduled_at": _schedule_widget(),
        }
        help_texts = {
            "slug": _("Leave blank to generate from the title."),
            "faq": _("One pair per block — a line starting “Q:” then a line starting “A:”."),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["description"].required = False
        _accept_datetime_local(self.fields["scheduled_at"])


class MenuForm(forms.ModelForm):
    class Meta:
        model = Menu
        fields = ["name", "slug"]
        help_texts = {
            "slug": _("Used in templates, e.g. “primary” (header) or “footer”."),
        }


class MenuItemForm(TranslatableModelForm):
    # ``label`` is a parler translated field — edited one language at a time via
    # the dashboard's ?language= tabs (DashboardTranslatableFormMixin).
    class Meta:
        model = MenuItem
        fields = ["parent", "label", "link_type", "url", "post", "page", "category"]
        help_texts = {
            "parent": _("Nest this item under another item in this menu (any depth)."),
            "label": _("Leave blank to use the linked item's title."),
            "url": _("Used only for the “Custom URL” link type."),
        }

    # Which field each link type requires.
    _REQUIRED_FOR = {
        LinkType.CUSTOM: "url",
        LinkType.POST: "post",
        LinkType.PAGE: "page",
        LinkType.CATEGORY: "category",
    }

    def __init__(self, *args, menu: Menu | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._menu = menu
        # Parent choices are any item in THIS menu except the item itself and any of
        # its descendants (selecting one would create a cycle). Scoped via the
        # repository (the ORM home).
        parent_field = cast(forms.ModelChoiceField, self.fields["parent"])
        instance = self.instance if self.instance.pk else None
        if menu is not None:
            parent_field.queryset = MenuItemRepository.eligible_parents(menu, exclude=instance)
        parent_field.required = False
        parent_field.empty_label = _("— Top level —")

    def clean(self):
        cleaned = super().clean()
        required = self._REQUIRED_FOR.get(cleaned.get("link_type"))
        if required and not cleaned.get(required):
            self.add_error(required, _("Required for this link type."))
        # Cycle prevention: a parent may be any item in the same menu except the
        # item itself or any of its descendants. The queryset already excludes
        # those, but re-check here so a forged POST can't slip a cycle through.
        parent = cleaned.get("parent")
        if parent is not None and self.instance.pk and self._menu is not None:
            forbidden = MenuItemRepository.descendant_ids(self._menu, self.instance)
            if parent.pk == self.instance.pk or parent.pk in forbidden:
                self.add_error("parent", _("An item can't be nested under itself or its children."))
        return cleaned


class CategoryForm(TranslatableModelForm):
    class Meta:
        model = Category
        fields = ["name", "slug", "parent", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False


class TagForm(TranslatableModelForm):
    class Meta:
        model = Tag
        fields = ["name", "slug"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False


class UserRoleForm(forms.ModelForm):
    """Edit a user's roles (groups) and active state — not their password."""

    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label=_("Roles"),
    )

    class Meta:
        model = User
        fields = ["is_active", "groups"]


class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = [
            "site_name",
            "tagline",
            "posts_per_page",
            "allow_comments",
            "comments_require_login",
        ]


class SeoSettingsForm(forms.ModelForm):
    class Meta:
        model = SeoSettings
        fields = [
            "og_site_name",
            "default_og_image",
            "default_meta_description",
            "twitter_handle",
            "google_analytics_id",
            "google_tag_manager_id",
            "google_site_verification",
            "bing_site_verification",
            "discourage_search",
        ]
        widgets = {"default_meta_description": forms.Textarea(attrs={"rows": 2})}

    def clean_google_analytics_id(self) -> str:
        value = self.cleaned_data["google_analytics_id"].strip()
        if value and not re.fullmatch(r"G-[A-Z0-9]+", value):
            raise forms.ValidationError(_("Expected a Measurement ID like G-XXXXXXXXXX."))
        return value

    def clean_google_tag_manager_id(self) -> str:
        value = self.cleaned_data["google_tag_manager_id"].strip()
        if value and not re.fullmatch(r"GTM-[A-Z0-9]+", value):
            raise forms.ValidationError(_("Expected a container ID like GTM-XXXXXXX."))
        return value

    def clean_social_profiles(self) -> str:
        # These become schema.org sameAs URLs; only allow real http(s) links.
        lines = [ln.strip() for ln in self.cleaned_data["social_profiles"].splitlines()]
        cleaned = [ln for ln in lines if ln]
        for url in cleaned:
            if not url.startswith(("http://", "https://")):
                raise forms.ValidationError(
                    _("“%(url)s” must be a full http(s) URL.") % {"url": url}
                )
        return "\n".join(cleaned)
