"""Core (landing page) services — orchestration for the public home view.

Keeps the home view at the HTTP boundary and delegates data access to the content
repositories (no ``Model.objects`` here), so the publish rule and query shape live
in one place.
"""

from __future__ import annotations

from apps.content.repositories import PostRepository, ServiceRepository

from .forms import ContactForm
from .signals import contact_received

# How many items the landing showcases per section.
_HOME_LIMIT = 3


def home_context() -> dict:
    """Recent published posts + featured published services for the landing page."""
    return {
        "recent_posts": PostRepository.recent_published(_HOME_LIMIT),
        "featured_services": ServiceRepository.recent_published(_HOME_LIMIT),
    }


def submit_contact(data) -> tuple[bool, ContactForm]:
    """Validate a contact submission and, if valid, emit ``contact_received``.

    Returns ``(sent, bound_form)``; on failure the form carries errors for
    re-render. The email is delivered by the observer (send_robust so a mail
    outage can't break the request) — no side effect runs inline here.
    """
    form = ContactForm(data)
    if form.is_valid():
        contact_received.send_robust(sender=ContactForm, cleaned=form.cleaned_data)
        return True, form
    return False, form
