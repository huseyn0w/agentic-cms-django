from __future__ import annotations

import os

from django import forms
from django.template.defaultfilters import filesizeformat
from django.utils.translation import gettext_lazy as _

from .constants import MAX_UPLOAD_SIZE
from .models import MediaAsset
from .sniff import UnsupportedUpload, extension_for_mime, sniff_mime


class MediaUploadForm(forms.ModelForm):
    class Meta:
        model = MediaAsset
        fields = ["file", "title", "alt_text"]
        # Stable hooks for the Playwright end-to-end upload journey.
        widgets = {
            "file": forms.ClearableFileInput(attrs={"data-testid": "media-file"}),
            "title": forms.TextInput(attrs={"data-testid": "media-title"}),
        }

    def clean_file(self):
        # Validate the file's actual BYTES, not the browser-supplied extension:
        # a renamed script / SVG / polyglot is rejected here regardless of its
        # name. SVG carries inline script and is an XSS vector, so it never
        # validates. The stored extension is then derived from the validated MIME
        # (anti-polyglot): a valid GIF named "evil.php" is stored as ".gif" and
        # can never be served as executable/text-html.
        uploaded = self.cleaned_data["file"]
        if uploaded.size > MAX_UPLOAD_SIZE:
            raise forms.ValidationError(
                _("File is too large (%(size)s). Maximum is %(max)s."),
                params={
                    "size": filesizeformat(uploaded.size),
                    "max": filesizeformat(MAX_UPLOAD_SIZE),
                },
            )
        try:
            mime = sniff_mime(uploaded)
        except UnsupportedUpload:
            raise forms.ValidationError(
                _(
                    "Unsupported or unsafe file. Allowed: JPEG, PNG, GIF, WebP, PDF "
                    "(SVG is not allowed)."
                )
            ) from None

        # Correct the stored filename's extension to match the validated MIME, so
        # the extension can never contradict the real bytes.
        canonical_ext = extension_for_mime(mime)
        base = os.path.splitext(os.path.basename(uploaded.name))[0] or "upload"
        uploaded.name = f"{base}{canonical_ext}"
        return uploaded
