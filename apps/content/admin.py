"""Interim Django admin for content.

This is developer-facing CRUD so content is editable before the bespoke
admin panel lands in Phase 5. Kept deliberately minimal. Models
are translated per language via django-parler, so the admin uses TranslatableAdmin
(translated fields are edited for the language tab shown at the top of the form).
"""

from django.contrib import admin
from parler.admin import TranslatableAdmin

from .models import Category, Page, PageRevision, Post, PostRevision, Tag


class PostRevisionInline(admin.TabularInline):
    model = PostRevision
    extra = 0
    can_delete = False
    readonly_fields = ("language_code", "title", "body", "author", "created_at")
    ordering = ("-created_at",)

    def has_add_permission(self, request, obj=None) -> bool:
        return False


@admin.register(Category)
class CategoryAdmin(TranslatableAdmin):
    list_display = ("name", "slug", "parent")
    search_fields = ("translations__name", "slug")


@admin.register(Tag)
class TagAdmin(TranslatableAdmin):
    list_display = ("name", "slug")
    search_fields = ("translations__name", "slug")


@admin.register(Post)
class PostAdmin(TranslatableAdmin):
    list_display = ("title", "author", "status", "published_at", "updated_at")
    list_filter = ("status", "categories", "tags")
    search_fields = ("translations__title", "translations__body")
    autocomplete_fields = ("categories", "tags")
    inlines = (PostRevisionInline,)


class PageRevisionInline(admin.TabularInline):
    model = PageRevision
    extra = 0
    can_delete = False
    readonly_fields = ("language_code", "title", "body", "author", "created_at")
    ordering = ("-created_at",)

    def has_add_permission(self, request, obj=None) -> bool:
        return False


@admin.register(Page)
class PageAdmin(TranslatableAdmin):
    list_display = ("title", "author", "status", "parent", "published_at")
    list_filter = ("status",)
    search_fields = ("translations__title", "translations__body")
    inlines = (PageRevisionInline,)
