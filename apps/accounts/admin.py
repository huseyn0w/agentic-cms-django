from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Django admin for the custom user — exposes the extra profile fields.

    This is interim tooling; the bespoke admin panel arrives in Phase 5.
    """

    list_display = ("username", "email", "display_name", "is_staff", "is_active")
    fieldsets = [
        *(DjangoUserAdmin.fieldsets or ()),
        (_("Profile"), {"fields": ("avatar", "bio", "website")}),
    ]
    add_fieldsets = [
        *(DjangoUserAdmin.add_fieldsets or ()),
        (_("Profile"), {"fields": ("bio", "website")}),
    ]
