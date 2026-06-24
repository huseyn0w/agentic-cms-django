from __future__ import annotations

import os

from django import forms
from django.template.defaultfilters import filesizeformat
from django.utils.translation import gettext_lazy as _

from .constants import ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE
from .models import MediaAsset


class MediaUploadForm(forms.ModelForm):
    class Meta:
        model = MediaAsset
        fields = ["file", "title", "alt_text"]

    def clean_file(self):
        # Validation is by extension + size (and SVG is excluded in constants).
        # We intentionally do NOT do magic-byte sniffing here — matching how most
        # popular CMSs operate. The real safety net is that uploads
        # are served with X-Content-Type-Options: nosniff and never executed.
        uploaded = self.cleaned_data["file"]
        ext = os.path.splitext(uploaded.name)[1].lstrip(".").lower()
        if ext not in ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
            raise forms.ValidationError(
                _("Unsupported file type “.%(ext)s”. Allowed: %(allowed)s."),
                params={"ext": ext, "allowed": allowed},
            )
        if uploaded.size > MAX_UPLOAD_SIZE:
            raise forms.ValidationError(
                _("File is too large (%(size)s). Maximum is %(max)s."),
                params={
                    "size": filesizeformat(uploaded.size),
                    "max": filesizeformat(MAX_UPLOAD_SIZE),
                },
            )
        return uploaded
