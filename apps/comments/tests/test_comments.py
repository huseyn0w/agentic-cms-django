"""Threaded, moderated comments: model, public flow, dashboard moderation."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse

from apps.comments.models import Comment, CommentStatus
from apps.content.models import Post, Status
from apps.core.models import SiteSettings

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def author():
    return User.objects.create_user(username="writer")


@pytest.fixture
def post(author):
    return Post.objects.create(
        title="Hello", body="<p>x</p>", author=author, status=Status.PUBLISHED
    )


def _approved(post, **kw):
    return Comment.objects.create(post=post, status=CommentStatus.APPROVED, **kw)


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #
def test_comment_defaults_to_pending(post):
    c = Comment.objects.create(post=post, name="Bob", body="Hi")
    assert c.status == CommentStatus.PENDING
    assert not c.is_approved


def test_approved_manager_and_replies(post):
    top = _approved(post, name="A", body="top")
    _approved(post, name="B", body="reply", parent=top)
    Comment.objects.create(post=post, name="C", body="pending reply", parent=top)  # pending
    assert Comment.objects.approved().count() == 2
    assert list(top.approved_replies().values_list("name", flat=True)) == ["B"]


# --------------------------------------------------------------------------- #
# Public submission + moderation gating
# --------------------------------------------------------------------------- #
def test_guest_submission_is_pending_and_hidden_until_approved(client, post):
    resp = client.post(
        post.get_absolute_url(), {"name": "Bob", "email": "b@x.com", "body": "Great post"}
    )
    assert resp.status_code == 302
    c = Comment.objects.get()
    assert c.status == CommentStatus.PENDING
    assert c.name == "Bob"

    # Hidden while pending.
    assert b"Great post" not in client.get(post.get_absolute_url()).content
    # Visible once approved.
    c.status = CommentStatus.APPROVED
    c.save()
    assert b"Great post" in client.get(post.get_absolute_url()).content


def test_logged_in_comment_uses_account_identity(client, post):
    user = User.objects.create_user(username="ada", password="pw", first_name="Ada")
    client.force_login(user)
    client.post(post.get_absolute_url(), {"body": "From Ada"})
    c = Comment.objects.get()
    assert c.user == user
    assert c.name  # display name filled from the account


def test_invalid_comment_rerenders_without_creating(client, post):
    resp = client.post(post.get_absolute_url(), {"name": "Bob", "body": ""})
    assert resp.status_code == 200
    assert Comment.objects.count() == 0


def test_reply_must_match_post(client, post, author):
    other = Post.objects.create(title="Other", author=author, status=Status.PUBLISHED)
    parent = _approved(other, name="X", body="elsewhere")
    client.post(
        post.get_absolute_url(), {"name": "B", "email": "", "body": "hi", "parent": parent.pk}
    )
    assert Comment.objects.filter(post=post).count() == 0  # rejected


def test_reply_to_unapproved_parent_is_rejected(client, post):
    pending_parent = Comment.objects.create(post=post, name="P", body="pending")
    client.post(
        post.get_absolute_url(),
        {"name": "B", "email": "", "body": "reply", "parent": pending_parent.pk},
    )
    # Only the pending parent exists; the reply was rejected (parent not approved).
    assert Comment.objects.count() == 1


def test_require_login_blocks_anonymous(client, post):
    site = SiteSettings.load()
    site.comments_require_login = True
    site.save()
    resp = client.post(post.get_absolute_url(), {"name": "Bob", "body": "hi"})
    assert resp.status_code == 302
    assert "/accounts/login/" in resp.url
    assert Comment.objects.count() == 0


def test_comments_disabled_returns_404_on_post(client, post):
    site = SiteSettings.load()
    site.allow_comments = False
    site.save()
    resp = client.post(post.get_absolute_url(), {"name": "Bob", "body": "hi"})
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Dashboard moderation
# --------------------------------------------------------------------------- #
def test_moderation_requires_permission(client, post):
    author = User.objects.create_user(username="auth", password="pw")
    author.groups.add(Group.objects.get(name="Author"))  # no moderate_comment
    client.force_login(author)
    assert client.get(reverse("dashboard:comment_list")).status_code == 403


def test_editor_can_approve_spam_delete(client, post):
    editor = User.objects.create_user(username="ed", password="pw")
    editor.groups.add(Group.objects.get(name="Editor"))
    client.force_login(editor)
    c = Comment.objects.create(post=post, name="Bob", body="hi")

    assert client.get(reverse("dashboard:comment_list")).status_code == 200

    client.post(reverse("dashboard:comment_moderate", args=[c.pk, "approve"]))
    c.refresh_from_db()
    assert c.status == CommentStatus.APPROVED

    client.post(reverse("dashboard:comment_moderate", args=[c.pk, "spam"]))
    c.refresh_from_db()
    assert c.status == CommentStatus.SPAM

    client.post(reverse("dashboard:comment_moderate", args=[c.pk, "delete"]))
    assert not Comment.objects.filter(pk=c.pk).exists()
