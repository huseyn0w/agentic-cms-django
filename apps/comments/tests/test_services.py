import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from apps.comments.models import Comment, CommentStatus
from apps.comments.services import (
    CREATED,
    DISABLED,
    INVALID,
    LOGIN_REQUIRED,
    moderate,
    submit_comment,
)
from apps.content.models import Post
from apps.core.models import SiteSettings

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def post():
    author = User.objects.create_user(username="auth", email="auth@example.com")
    return Post.objects.create(title="A post", author=author)


# --------------------------------------------------------------------------- #
# Target B: submit_comment(post, user, data)
# --------------------------------------------------------------------------- #
def test_submit_comment_guest_creates_pending_comment(post):
    data = {"name": "Guest", "email": "g@example.com", "body": "Nice post"}
    outcome, form = submit_comment(post, AnonymousUser(), data)
    assert outcome == CREATED
    comment = Comment.objects.get(post=post)
    assert comment.status == CommentStatus.PENDING
    assert comment.name == "Guest"
    assert comment.user is None


def test_submit_comment_authenticated_takes_identity_from_account(post):
    user = User.objects.create_user(
        username="reader", email="reader@example.com", first_name="Read", last_name="Er"
    )
    outcome, _form = submit_comment(post, user, {"body": "From my account"})
    assert outcome == CREATED
    comment = Comment.objects.get(post=post)
    assert comment.user == user
    assert comment.name == user.display_name
    assert comment.email == "reader@example.com"


def test_submit_comment_invalid_returns_form_with_errors_and_saves_nothing(post):
    outcome, form = submit_comment(post, AnonymousUser(), {"name": "X", "email": "", "body": ""})
    assert outcome == INVALID
    assert form.errors
    assert Comment.objects.filter(post=post).count() == 0


def test_submit_comment_disabled_returns_disabled(post):
    site = SiteSettings.load()
    site.allow_comments = False
    site.save()
    outcome, form = submit_comment(post, AnonymousUser(), {"name": "G", "body": "hi"})
    assert outcome == DISABLED
    assert form is None
    assert Comment.objects.count() == 0


def test_submit_comment_login_required_blocks_anonymous(post):
    site = SiteSettings.load()
    site.comments_require_login = True
    site.save()
    outcome, form = submit_comment(post, AnonymousUser(), {"name": "G", "body": "hi"})
    assert outcome == LOGIN_REQUIRED
    assert form is None
    assert Comment.objects.count() == 0


# --------------------------------------------------------------------------- #
# Target C: Comment.approve() / mark_spam() + moderate(comment, action)
# --------------------------------------------------------------------------- #
@pytest.fixture
def pending_comment(post):
    return Comment.objects.create(post=post, name="G", email="g@example.com", body="hi")


def test_comment_approve_persists_status(pending_comment):
    pending_comment.approve()
    pending_comment.refresh_from_db()
    assert pending_comment.status == CommentStatus.APPROVED


def test_comment_mark_spam_persists_status(pending_comment):
    pending_comment.mark_spam()
    pending_comment.refresh_from_db()
    assert pending_comment.status == CommentStatus.SPAM


def test_moderate_approve(pending_comment):
    msg = moderate(pending_comment, "approve")
    pending_comment.refresh_from_db()
    assert pending_comment.status == CommentStatus.APPROVED
    assert "approved" in msg.lower()


def test_moderate_spam(pending_comment):
    moderate(pending_comment, "spam")
    pending_comment.refresh_from_db()
    assert pending_comment.status == CommentStatus.SPAM


def test_moderate_delete_removes_comment(pending_comment):
    pk = pending_comment.pk
    moderate(pending_comment, "delete")
    assert not Comment.objects.filter(pk=pk).exists()


def test_moderate_unknown_action_raises(pending_comment):
    with pytest.raises(ValueError):
        moderate(pending_comment, "explode")
