"""SSE (streaming) MCP transport.

A ``GET /api/mcp/sse`` endpoint that reuses the same tool registry, the same
``services.call_tool``, and the same auth floor as the JSON endpoint. It emits
MCP-style ``text/event-stream`` events: an initial ``tools/list`` event, and —
when a tool name is supplied — a streamed ``tools/call`` result event.
"""

import json

import pytest

from apps.content.models import Post, Status

pytestmark = pytest.mark.django_db

URL = "/api/mcp/sse"


def _body(response) -> str:
    return b"".join(response.streaming_content).decode("utf-8")


def test_sse_rejects_anonymous(client):
    response = client.get(URL)
    assert response.status_code in (401, 403)


def test_sse_returns_event_stream(client, make_user, auth_headers):
    editor = make_user("ed", role="Editor")
    response = client.get(URL, **auth_headers(editor))
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/event-stream")


def test_sse_streams_tools_list(client, make_user, auth_headers):
    editor = make_user("ed", role="Editor")
    response = client.get(URL, **auth_headers(editor))
    body = _body(response)
    assert "event: tools/list" in body
    assert "posts.create" in body


def test_sse_streams_tool_call_result(client, make_user, auth_headers):
    boss = make_user("boss", role="Administrator")
    Post.objects.create(title="Streamed", author=boss, status=Status.PUBLISHED)
    response = client.get(
        URL,
        {"name": "posts.list", "arguments": json.dumps({})},
        **auth_headers(boss),
    )
    body = _body(response)
    assert "event: tools/call" in body
    assert "Streamed" in body


def test_sse_tool_call_forbidden_streams_error(client, make_user, auth_headers):
    sub = make_user("sub", role="Subscriber")  # no content perms
    response = client.get(
        URL, {"name": "posts.create", "arguments": json.dumps({"title": "X"})}, **auth_headers(sub)
    )
    # The connection still opens (200, auth floor passed) but the tool call
    # re-verification denies the call and the error is streamed as an event.
    body = _body(response)
    assert "event: error" in body
    assert "forbidden" in body
    assert Post.objects.count() == 0


def test_sse_oauth_works(client, make_user, oauth_bearer):
    editor = make_user("ed", role="Editor")
    response = client.get(URL, **oauth_bearer(editor))
    assert response.status_code == 200
    body = _body(response)
    assert "event: tools/list" in body


# --------------------------------------------------------------------------- #
# Per-tool OAuth scope gate over SSE: a read-scope token cannot run a write tool.
# --------------------------------------------------------------------------- #
def test_sse_read_scope_cannot_run_write_tool(client, make_user, oauth_bearer):
    author = make_user("a", role="Author")  # has add_post
    response = client.get(
        URL,
        {"name": "posts.create", "arguments": json.dumps({"title": "X"})},
        **oauth_bearer(author, scope="read"),
    )
    body = _body(response)
    assert "event: error" in body
    assert "forbidden" in body
    assert Post.objects.count() == 0


def test_sse_write_scope_can_run_write_tool(client, make_user, oauth_bearer):
    author = make_user("a", role="Author")
    response = client.get(
        URL,
        {"name": "posts.create", "arguments": json.dumps({"title": "Streamed write"})},
        **oauth_bearer(author, scope="read write"),
    )
    body = _body(response)
    assert "event: tools/call" in body
    assert "Streamed write" in body
    assert Post.objects.get().author == author


def test_sse_token_auth_write_tool_not_scope_gated(client, make_user, auth_headers):
    author = make_user("a", role="Author")
    response = client.get(
        URL,
        {"name": "posts.create", "arguments": json.dumps({"title": "Tok stream"})},
        **auth_headers(author),
    )
    body = _body(response)
    assert "event: tools/call" in body
    assert Post.objects.get().author == author
