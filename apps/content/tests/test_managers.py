import pytest
from django.contrib.auth import get_user_model

from apps.content.models import Post, Status

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def authors():
    alice = User.objects.create_user(username="alice", email="a@example.com")
    bob = User.objects.create_user(username="bob", email="b@example.com")
    return alice, bob


# --------------------------------------------------------------------------- #
# Target A: Post.objects.editable_by(user)
# --------------------------------------------------------------------------- #
def test_editable_by_returns_all_for_user_with_delete_perm(authors):
    alice, bob = authors
    Post.objects.create(title="Alice post", author=alice)
    Post.objects.create(title="Bob post", author=bob)
    manager = User.objects.create_superuser(
        username="boss", email="boss@example.com", password="pw"
    )
    editable = Post.objects.editable_by(manager)
    assert editable.count() == 2


def test_editable_by_scopes_to_own_posts_without_delete_perm(authors):
    alice, bob = authors
    alice_post = Post.objects.create(title="Alice post", author=alice)
    Post.objects.create(title="Bob post", author=bob)
    editable = Post.objects.editable_by(alice)
    assert list(editable) == [alice_post]


def test_editable_by_is_chainable_with_published(authors):
    alice, _ = authors
    Post.objects.create(title="Alice draft", author=alice)
    live = Post.objects.create(title="Alice live", author=alice, status=Status.PUBLISHED)
    # editable_by returns a queryset, so it composes with the publish filter.
    assert list(Post.objects.editable_by(alice).published()) == [live]


# --------------------------------------------------------------------------- #
# Target D: Post.gate_publish_state(user)
# --------------------------------------------------------------------------- #
def test_gate_publish_state_forces_draft_on_new_post_without_publish_perm(authors):
    alice, _ = authors
    post = Post(author=alice, status=Status.PUBLISHED)  # unsaved, no pk
    post.gate_publish_state(alice)  # alice lacks publish_post
    assert post.status == Status.DRAFT


def test_gate_publish_state_preserves_stored_status_on_edit_without_perm(authors):
    alice, _ = authors
    post = Post.objects.create(title="Live", author=alice, status=Status.PUBLISHED)
    # Simulate an edit that tries to unpublish.
    post.status = Status.DRAFT
    post.gate_publish_state(alice)  # alice lacks publish_post -> keep stored PUBLISHED
    assert post.status == Status.PUBLISHED


def test_gate_publish_state_is_noop_for_user_with_publish_perm(authors):
    alice, _ = authors
    manager = User.objects.create_superuser(
        username="boss", email="boss@example.com", password="pw"
    )
    post = Post.objects.create(title="Draft", author=alice, status=Status.DRAFT)
    post.status = Status.PUBLISHED
    post.gate_publish_state(manager)  # superuser may publish -> unchanged
    assert post.status == Status.PUBLISHED
