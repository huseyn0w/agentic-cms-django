"""Gated write API for posts + token issuance (F12b)."""

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.authtoken.models import Token

from apps.api import services
from apps.content.models import Post, Status

pytestmark = pytest.mark.django_db


def _auth(user):
    return {"HTTP_AUTHORIZATION": f"Token {Token.objects.create(user=user).key}"}


def _post_json(client, url, payload, **extra):
    return client.post(url, data=json.dumps(payload), content_type="application/json", **extra)


# --------------------------------------------------------------------------- #
# Auth gating
# --------------------------------------------------------------------------- #
def test_anonymous_cannot_create(client):
    response = _post_json(client, "/api/v1/posts/", {"title": "Nope"})
    assert response.status_code in (401, 403)
    assert Post.objects.count() == 0


def test_author_can_create_own_post(client, make_user):
    author = make_user("writer", role="Author")
    response = _post_json(client, "/api/v1/posts/", {"title": "Hello API"}, **_auth(author))
    assert response.status_code == 201
    post = Post.objects.get()
    assert post.author == author
    assert post.safe_translation_getter("title") == "Hello API"


def test_non_publisher_cannot_publish_via_api(client, make_user):
    contributor = make_user("contrib", role="Contributor")  # add_post, no publish_post
    response = _post_json(
        client, "/api/v1/posts/", {"title": "Sneaky", "status": "published"}, **_auth(contributor)
    )
    assert response.status_code == 201
    assert Post.objects.get().status == Status.DRAFT


def test_publisher_can_publish_via_api(client, make_user):
    author = make_user("writer", role="Author")  # has publish_post
    _post_json(client, "/api/v1/posts/", {"title": "Live", "status": "published"}, **_auth(author))
    post = Post.objects.get()
    assert post.status == Status.PUBLISHED
    assert post.published_at is not None


# --------------------------------------------------------------------------- #
# Ownership + permissions
# --------------------------------------------------------------------------- #
def test_author_can_update_own_post(client, make_user):
    author = make_user("a", role="Author")
    post = Post.objects.create(title="Old", author=author)
    response = client.patch(
        f"/api/v1/posts/{post.slug}/",
        data=json.dumps({"title": "New title"}),
        content_type="application/json",
        **_auth(author),
    )
    assert response.status_code == 200
    post.refresh_from_db()
    assert post.safe_translation_getter("title") == "New title"


def test_author_cannot_edit_another_authors_post(client, make_user):
    a = make_user("a", role="Author")
    b = make_user("b", role="Author")
    post = Post.objects.create(title="A's", author=a, status=Status.PUBLISHED)
    response = client.patch(
        f"/api/v1/posts/{post.slug}/",
        data=json.dumps({"title": "Hijacked"}),
        content_type="application/json",
        **_auth(b),
    )
    assert response.status_code == 404


def test_author_cannot_delete_without_perm(client, make_user):
    author = make_user("a", role="Author")  # no delete_post
    post = Post.objects.create(title="Mine", author=author)
    response = client.delete(f"/api/v1/posts/{post.slug}/", **_auth(author))
    assert response.status_code == 403
    assert Post.objects.filter(pk=post.pk).exists()


def test_editor_can_delete(client, make_user):
    editor = make_user("ed", role="Editor")
    post = Post.objects.create(title="Doomed", author=editor)
    response = client.delete(f"/api/v1/posts/{post.slug}/", **_auth(editor))
    assert response.status_code == 204
    assert not Post.objects.filter(pk=post.pk).exists()


# --------------------------------------------------------------------------- #
# Token issuance
# --------------------------------------------------------------------------- #
def test_issue_token_returns_key(make_user):
    user = make_user("client")
    key = services.issue_token("client")
    assert key
    assert Token.objects.get(user=user).key == key


def test_issue_token_unknown_user_is_none(db):
    assert services.issue_token("ghost") is None


def test_create_api_token_command(make_user):
    make_user("cli")
    out = StringIO()
    call_command("create_api_token", "cli", stdout=out)
    assert out.getvalue().strip()  # prints the key


def test_create_api_token_command_unknown_user(db):
    with pytest.raises(CommandError):
        call_command("create_api_token", "nobody")
