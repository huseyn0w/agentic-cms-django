"""F5 — comment-notification email via the service→signal→observer pattern."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from apps.comments.models import Comment
from apps.comments.services import CREATED, submit_comment
from apps.content.models import Post

User = get_user_model()
pytestmark = pytest.mark.django_db


def _post(author):
    return Post.objects.create(title="Notify me", author=author)


def test_submitting_comment_emails_the_post_author(mailoutbox):
    author = User.objects.create_user(username="auth", email="author@example.com")
    post = _post(author)

    outcome, _ = submit_comment(post, AnonymousUser(), {"name": "Guest", "body": "Nice!"})

    assert outcome == CREATED
    assert len(mailoutbox) == 1
    mail = mailoutbox[0]
    assert mail.to == ["author@example.com"]
    assert "Notify me" in mail.subject
    assert "Nice!" in mail.body


def test_no_email_when_author_has_no_address(mailoutbox):
    author = User.objects.create_user(username="auth")  # no email
    post = _post(author)

    submit_comment(post, AnonymousUser(), {"name": "Guest", "body": "Hi"})

    assert mailoutbox == []


def test_invalid_comment_sends_no_email(mailoutbox):
    author = User.objects.create_user(username="auth", email="author@example.com")
    post = _post(author)

    submit_comment(post, AnonymousUser(), {"name": "Guest", "body": ""})  # invalid

    assert mailoutbox == []
    assert Comment.objects.count() == 0


def test_mail_failure_does_not_break_submission(monkeypatch):
    """A failing observer (mail outage) must not affect the visitor's submission."""
    author = User.objects.create_user(username="auth", email="author@example.com")
    post = _post(author)

    def boom(*args, **kwargs):
        raise RuntimeError("smtp down")

    monkeypatch.setattr("apps.comments.signals.send_mail", boom)

    outcome, _ = submit_comment(post, AnonymousUser(), {"name": "Guest", "body": "Still ok"})

    assert outcome == CREATED  # send_robust swallowed the receiver error
    assert Comment.objects.filter(post=post).count() == 1
