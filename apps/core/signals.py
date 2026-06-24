"""Core domain events + observers. Side effects run here, never inline in a
service (architecture rule 2).

``contact_received`` is emitted by ``apps.core.services.submit_contact``; the
observer emails the site's configured recipient (``settings.CONTACT_EMAIL``).
"""

from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMessage
from django.dispatch import Signal, receiver

# Domain event: a contact-form message was submitted. providing arg: cleaned (dict).
contact_received = Signal()


@receiver(contact_received, dispatch_uid="core.email_contact_message")
def email_contact_message(sender, cleaned, **kwargs) -> None:
    """Deliver a contact message to the configured recipient (no-op if unset)."""
    recipient = getattr(settings, "CONTACT_EMAIL", "") or ""
    if not recipient:
        return
    name = cleaned.get("name", "")
    email = cleaned.get("email", "")
    subject = f"Contact form: {name}"
    body = f"From: {name} <{email}>\n\n{cleaned.get('message', '')}\n"
    message = EmailMessage(
        subject, body, to=[recipient], reply_to=[email] if email else None
    )
    message.send(fail_silently=True)
