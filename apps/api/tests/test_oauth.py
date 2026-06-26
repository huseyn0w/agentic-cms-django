"""OAuth 2.1 auth floor for the API (django-oauth-toolkit).

OAuth is an ADDITIONAL authentication method alongside Token + Session auth.
It authenticates the caller; the existing model-permission gates still own
authorization (owner-scoping, publish-gating, scope read/write).
"""

import json

import pytest
from rest_framework.authtoken.models import Token

from apps.content.models import Post, Status

pytestmark = pytest.mark.django_db


def _post_json(client, url, payload, **extra):
    return client.post(url, data=json.dumps(payload), content_type="application/json", **extra)


# --------------------------------------------------------------------------- #
# Provider endpoints are mounted at /oauth/ (outside i18n)
# --------------------------------------------------------------------------- #
def test_authorize_endpoint_mounted_redirects_anonymous(client):
    response = client.get("/oauth/authorize/")
    # Mounted (not 404): anonymous hits the login redirect, not a missing route.
    assert response.status_code != 404
    assert response.status_code in (302, 400, 403)


def test_token_endpoint_mounted(client):
    # GET on the token endpoint is not allowed, but it must exist (not 404).
    response = client.get("/oauth/token/")
    assert response.status_code != 404


# --------------------------------------------------------------------------- #
# (a) An authenticated read works with a Bearer token
# --------------------------------------------------------------------------- #
def test_oauth_read_works(client, make_user, oauth_bearer):
    user = make_user("reader")
    Post.objects.create(title="Public", author=user, status=Status.PUBLISHED)
    response = client.get("/api/v1/posts/", **oauth_bearer(user, scope="read"))
    assert response.status_code == 200


# --------------------------------------------------------------------------- #
# (b) A write works when the user has the permission AND a write-scoped token
# --------------------------------------------------------------------------- #
def test_oauth_write_works_with_permission(client, make_user, oauth_bearer):
    author = make_user("writer", role="Author")  # add_post
    response = _post_json(
        client, "/api/v1/posts/", {"title": "Via OAuth"}, **oauth_bearer(author, scope="read write")
    )
    assert response.status_code == 201
    assert Post.objects.get().author == author


def test_oauth_read_scope_cannot_write(client, make_user, oauth_bearer):
    # The user HAS the model permission, but the token only carries "read" scope:
    # the OAuth scope floor must still deny the write.
    author = make_user("writer", role="Author")
    response = _post_json(
        client, "/api/v1/posts/", {"title": "Scoped out"}, **oauth_bearer(author, scope="read")
    )
    assert response.status_code == 403
    assert Post.objects.count() == 0


def test_oauth_write_without_permission_is_forbidden(client, make_user, oauth_bearer):
    sub = make_user("sub", role="Subscriber")  # no add_post
    response = _post_json(
        client, "/api/v1/posts/", {"title": "Nope"}, **oauth_bearer(sub, scope="read write")
    )
    assert response.status_code == 403
    assert Post.objects.count() == 0


# --------------------------------------------------------------------------- #
# (c) Invalid / expired tokens are rejected (401)
# --------------------------------------------------------------------------- #
def test_invalid_token_rejected_on_write(client, make_user):
    make_user("writer", role="Author")
    response = _post_json(
        client,
        "/api/v1/posts/",
        {"title": "X"},
        HTTP_AUTHORIZATION="Bearer not-a-real-token",
    )
    assert response.status_code in (401, 403)
    assert Post.objects.count() == 0


def test_expired_token_rejected_on_write(client, make_user, oauth_bearer):
    author = make_user("writer", role="Author")
    response = _post_json(
        client,
        "/api/v1/posts/",
        {"title": "X"},
        **oauth_bearer(author, scope="read write", expired=True),
    )
    assert response.status_code in (401, 403)
    assert Post.objects.count() == 0


# --------------------------------------------------------------------------- #
# (d) Existing Token + Session auth still work
# --------------------------------------------------------------------------- #
def test_token_auth_still_works(client, make_user):
    author = make_user("writer", role="Author")
    headers = {"HTTP_AUTHORIZATION": f"Token {Token.objects.create(user=author).key}"}
    response = _post_json(client, "/api/v1/posts/", {"title": "Token auth"}, **headers)
    assert response.status_code == 201


def test_session_auth_still_works(client, make_user):
    author = make_user("writer", role="Author")
    client.force_login(author)
    response = _post_json(client, "/api/v1/posts/", {"title": "Session auth"})
    assert response.status_code == 201
