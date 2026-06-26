from __future__ import annotations

from django import forms
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV3

from apps.comments.forms import recaptcha_enabled


class ContactForm(forms.Form):
    """Public contact form. Email-only (no persistence); delivered to the
    site's configured recipient by a signal observer. reCAPTCHA v3 is added only
    when keys are configured (same graceful pattern as the comment form)."""

    name = forms.CharField(max_length=120)
    email = forms.EmailField()
    message = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 5, "placeholder": "How can we help?"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if recaptcha_enabled():
            self.fields["captcha"] = ReCaptchaField(widget=ReCaptchaV3())
