from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()


class ProfileForm(forms.ModelForm):
    """Self-service profile editor. Email/username/roles are intentionally absent."""

    class Meta:
        model = User
        fields = ["first_name", "last_name", "bio", "website", "avatar"]
        widgets = {"bio": forms.Textarea(attrs={"rows": 4})}
        help_texts = {"bio": "Shown on your public author page."}
