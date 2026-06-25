from __future__ import annotations

import re
from typing import cast

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
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
            "slug": "Leave blank to generate from the title.",
            "meta_title": "Overrides the page title in search results (≤70 chars).",
            "meta_description": "Shown in search results; falls back to the excerpt.",
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
        help_texts = {"slug": "Leave blank to generate from the title."}

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
            "slug": "Leave blank to generate from the title.",
            "faq": "One pair per block — a line starting “Q:” then a line starting “A:”.",
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
            "slug": "Used in templates, e.g. “primary” (header) or “footer”.",
        }


class MenuItemForm(forms.ModelForm):
    class Meta:
        model = MenuItem
        fields = ["parent", "label", "link_type", "url", "post", "page", "category"]
        help_texts = {
            "parent": "Nest this item under a top-level item (one level deep).",
            "label": "Leave blank to use the linked item's title.",
            "url": "Used only for the “Custom URL” link type.",
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
        # Parent choices are this menu's top-level items only (one-level nesting),
        # never the item itself. Scoped via the repository (the ORM home).
        parent_field = cast(forms.ModelChoiceField, self.fields["parent"])
        instance = self.instance if self.instance.pk else None
        if menu is not None:
            parent_field.queryset = MenuItemRepository.top_level_choices(menu, exclude=instance)
        parent_field.required = False
        parent_field.empty_label = "— Top level —"

    def clean(self):
        cleaned = super().clean()
        required = self._REQUIRED_FOR.get(cleaned.get("link_type"))
        if required and not cleaned.get(required):
            self.add_error(required, "Required for this link type.")
        # One level only: an item that already has children can't itself be nested.
        parent = cleaned.get("parent")
        if parent is not None and self.instance.pk and self.instance.children.exists():
            self.add_error("parent", "This item has sub-items; move those out first.")
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
        label="Roles",
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
            raise forms.ValidationError("Expected a Measurement ID like G-XXXXXXXXXX.")
        return value

    def clean_google_tag_manager_id(self) -> str:
        value = self.cleaned_data["google_tag_manager_id"].strip()
        if value and not re.fullmatch(r"GTM-[A-Z0-9]+", value):
            raise forms.ValidationError("Expected a container ID like GTM-XXXXXXX.")
        return value

    def clean_social_profiles(self) -> str:
        # These become schema.org sameAs URLs; only allow real http(s) links.
        lines = [ln.strip() for ln in self.cleaned_data["social_profiles"].splitlines()]
        cleaned = [ln for ln in lines if ln]
        for url in cleaned:
            if not url.startswith(("http://", "https://")):
                raise forms.ValidationError(f"“{url}” must be a full http(s) URL.")
        return "\n".join(cleaned)
