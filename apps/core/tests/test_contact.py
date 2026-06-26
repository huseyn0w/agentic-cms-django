"""F4 — public contact form (email-only, via service→signal→observer)."""

import pytest
from django.test import override_settings
from django.urls import reverse

pytestmark = pytest.mark.django_db

_VALID = {"name": "Ada", "email": "ada@example.com", "message": "Hello there"}


def test_contact_page_renders(client):
    resp = client.get(reverse("core:contact"))
    assert resp.status_code == 200
    assert b"Contact" in resp.content


@override_settings(CONTACT_EMAIL="owner@example.com")
def test_valid_submission_emails_recipient_and_redirects(client, mailoutbox):
    resp = client.post(reverse("core:contact"), _VALID)
    assert resp.status_code == 302
    assert len(mailoutbox) == 1
    mail = mailoutbox[0]
    assert mail.to == ["owner@example.com"]
    assert mail.reply_to == ["ada@example.com"]
    assert "Hello there" in mail.body


@override_settings(CONTACT_EMAIL="")
def test_valid_submission_without_recipient_is_graceful(client, mailoutbox):
    resp = client.post(reverse("core:contact"), _VALID)
    assert resp.status_code == 302  # still thanks the visitor
    assert mailoutbox == []  # nothing sent, no error


@override_settings(CONTACT_EMAIL="owner@example.com")
def test_invalid_submission_rerenders_and_sends_nothing(client, mailoutbox):
    resp = client.post(reverse("core:contact"), {"name": "", "email": "nope", "message": ""})
    assert resp.status_code == 200
    assert mailoutbox == []
