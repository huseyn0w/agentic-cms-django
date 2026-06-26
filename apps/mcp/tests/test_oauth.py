"""OAuth 2.1 auth floor for the MCP JSON endpoint.

OAuth Bearer tokens authenticate alongside Token + Session auth; the per-tool
permission re-verification in ``services.call_tool`` still owns authorization.
"""

import json

import pytest

from apps.content.models import Post

pytestmark = pytest.mark.django_db

URL = "/api/mcp/"


def _rpc(client, payload, **extra):
    return client.post(URL, data=json.dumps(payload), content_type="application/json", **extra)


def test_oauth_tools_list_works(client, make_user, oauth_bearer):
    editor = make_user("ed", role="Editor")
    data = _rpc(client, {"method": "tools/list"}, **oauth_bearer(editor)).json()
    names = {t["name"] for t in data["result"]["tools"]}
    assert "posts.create" in names


def test_oauth_tools_call_with_permission(client, make_user, oauth_bearer):
    author = make_user("a", role="Author")  # add_post
    data = _rpc(
        client,
        {
            "method": "tools/call",
            "params": {"name": "posts.create", "arguments": {"title": "OAuth"}},
        },
        **oauth_bearer(author, scope="read write"),
    ).json()
    assert data["result"]["title"] == "OAuth"
    assert Post.objects.get().author == author


def test_oauth_tools_call_without_permission_forbidden(client, make_user, oauth_bearer):
    sub = make_user("sub", role="Subscriber")  # no content perms
    response = _rpc(
        client,
        {"method": "tools/call", "params": {"name": "posts.create", "arguments": {"title": "X"}}},
        **oauth_bearer(sub),
    )
    assert response.status_code == 403
    assert Post.objects.count() == 0


def test_oauth_invalid_token_rejected(client, make_user):
    make_user("ed", role="Editor")
    response = _rpc(client, {"method": "tools/list"}, HTTP_AUTHORIZATION="Bearer not-real")
    assert response.status_code in (401, 403)


def test_oauth_expired_token_rejected(client, make_user, oauth_bearer):
    editor = make_user("ed", role="Editor")
    response = _rpc(client, {"method": "tools/list"}, **oauth_bearer(editor, expired=True))
    assert response.status_code in (401, 403)


# --------------------------------------------------------------------------- #
# Per-tool OAuth scope gate (JSON endpoint): write tools require "write" scope,
# even though they ride a POST. Read tools work with a read-only scope.
# --------------------------------------------------------------------------- #
def test_read_scope_cannot_run_write_tool(client, make_user, oauth_bearer):
    # The user HAS add_post, but the token only carries "read" scope.
    author = make_user("a", role="Author")
    response = _rpc(
        client,
        {"method": "tools/call", "params": {"name": "posts.create", "arguments": {"title": "X"}}},
        **oauth_bearer(author, scope="read"),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert Post.objects.count() == 0


def test_empty_scope_cannot_run_write_tool(client, make_user, oauth_bearer):
    author = make_user("a", role="Author")
    response = _rpc(
        client,
        {"method": "tools/call", "params": {"name": "posts.create", "arguments": {"title": "X"}}},
        **oauth_bearer(author, scope=""),
    )
    assert response.status_code in (401, 403)
    assert Post.objects.count() == 0


def test_write_scope_can_run_write_tool(client, make_user, oauth_bearer):
    author = make_user("a", role="Author")
    data = _rpc(
        client,
        {"method": "tools/call", "params": {"name": "posts.create", "arguments": {"title": "OK"}}},
        **oauth_bearer(author, scope="read write"),
    ).json()
    assert data["result"]["title"] == "OK"
    assert Post.objects.get().author == author


def test_read_scope_can_run_read_tool(client, make_user, oauth_bearer):
    boss = make_user("boss", role="Administrator")
    Post.objects.create(title="P", author=boss)
    data = _rpc(
        client,
        {"method": "tools/call", "params": {"name": "posts.list", "arguments": {}}},
        **oauth_bearer(boss, scope="read"),
    ).json()
    assert "posts" in data["result"]


def test_token_auth_write_tool_not_scope_gated(client, make_user, auth_headers):
    # Token auth is not OAuth-scoped; the scope gate must NOT apply to it.
    author = make_user("a", role="Author")
    data = _rpc(
        client,
        {"method": "tools/call", "params": {"name": "posts.create", "arguments": {"title": "Tok"}}},
        **auth_headers(author),
    ).json()
    assert data["result"]["title"] == "Tok"
    assert Post.objects.get().author == author
