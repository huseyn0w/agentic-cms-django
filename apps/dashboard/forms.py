from __future__ import annotations

import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from parler.forms import TranslatableModelForm

from apps.content.models import Category, Page, Post, Tag
from apps.core.models import SiteSettings
from apps.seo.models import SeoSettings

User = get_user_model()


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
        if not can_publish:
            # Non-publishers can't change publish state at all, so don't offer the
            # field; the view preserves the stored status (see PublishGatingMixin).
            del self.fields["status"]


class PageForm(TranslatableModelForm):
    class Meta:
        model = Page
        fields = [
            "title",
            "slug",
            "body",
            "template",
            "status",
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
        }
        help_texts = {"slug": "Leave blank to generate from the title."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["body"].required = False


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
        fields = ["site_name", "tagline", "posts_per_page"]


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
