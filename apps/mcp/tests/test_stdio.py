"""Stdio MCP transport: JSON-RPC dispatch (unit) + the command end-to-end."""

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.content.models import Post
from apps.mcp import services

pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------------- #
# Unit: handle_jsonrpc (no stdio)
# --------------------------------------------------------------------------- #
def test_initialize_returns_server_info(make_user):
    user = make_user("ed", role="Editor")
    resp = services.handle_jsonrpc(user, {"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert resp["id"] == 1
    assert resp["result"]["serverInfo"]["name"]
    assert "capabilities" in resp["result"]


def test_ping(make_user):
    user = make_user("ed", role="Editor")
    resp = services.handle_jsonrpc(user, {"jsonrpc": "2.0", "id": 7, "method": "ping"})
    assert resp == {"jsonrpc": "2.0", "id": 7, "result": {}}


def test_tools_list_returns_schemas(make_user):
    user = make_user("ed", role="Editor")
    resp = services.handle_jsonrpc(user, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = {t["name"] for t in resp["result"]["tools"]}
    assert {"posts.list", "posts.create", "comments.moderate"} <= names


def test_tools_call_read_tool_works(make_user):
    boss = make_user("boss", role="Administrator")
    Post.objects.create(title="P", author=boss)
    resp = services.handle_jsonrpc(
        boss,
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "posts.list", "arguments": {}},
        },
    )
    assert "posts" in resp["result"]["content"]


def test_tools_call_write_tool_denied_without_perm(make_user):
    sub = make_user("sub", role="Subscriber")  # no content perms
    resp = services.handle_jsonrpc(
        sub,
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "posts.create", "arguments": {"title": "X"}},
        },
    )
    assert "error" in resp
    assert resp["error"]["code"] == -32000  # forbidden
    assert Post.objects.count() == 0


def test_tools_call_write_tool_succeeds_with_perm(make_user):
    author = make_user("a", role="Author")  # has add_post
    resp = services.handle_jsonrpc(
        author,
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "posts.create", "arguments": {"title": "Made"}},
        },
    )
    assert resp["result"]["content"]["title"] == "Made"
    assert Post.objects.get().author == author


def test_unknown_method_is_method_not_found(make_user):
    user = make_user("ed", role="Editor")
    resp = services.handle_jsonrpc(user, {"jsonrpc": "2.0", "id": 6, "method": "bogus"})
    assert resp["error"]["code"] == -32601


def test_notification_returns_none(make_user):
    user = make_user("ed", role="Editor")
    # No "id" → a notification → no response.
    resp = services.handle_jsonrpc(user, {"jsonrpc": "2.0", "method": "ping"})
    assert resp is None


def test_notification_unknown_method_returns_none(make_user):
    user = make_user("ed", role="Editor")
    resp = services.handle_jsonrpc(user, {"jsonrpc": "2.0", "method": "bogus"})
    assert resp is None


# --------------------------------------------------------------------------- #
# End-to-end: the management command over stdin/stdout
# --------------------------------------------------------------------------- #
def _run(username, lines):
    stdin = StringIO("\n".join(lines) + "\n")
    out = StringIO()
    call_command("mcp_stdio", "--user", username, stdin=stdin, stdout=out)
    return [json.loads(line) for line in out.getvalue().splitlines() if line.strip()]


def test_command_dispatches_lines(make_user):
    make_user("runner", role="Editor")
    responses = _run(
        "runner",
        [
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
        ],
    )
    assert responses[0]["id"] == 1
    assert responses[0]["result"]["serverInfo"]["name"]
    assert {t["name"] for t in responses[1]["result"]["tools"]}


def test_command_malformed_line_yields_parse_error_and_continues(make_user):
    make_user("runner", role="Editor")
    responses = _run(
        "runner",
        [
            "this is not json",
            json.dumps({"jsonrpc": "2.0", "id": 9, "method": "ping"}),
        ],
    )
    # First response is a parse error; the loop survived and answered the next line.
    assert responses[0]["error"]["code"] == -32700
    assert responses[0]["id"] is None
    assert responses[1] == {"jsonrpc": "2.0", "id": 9, "result": {}}


def test_command_notification_produces_no_line(make_user):
    make_user("runner", role="Editor")
    responses = _run(
        "runner",
        [
            json.dumps({"jsonrpc": "2.0", "method": "ping"}),  # notification
            json.dumps({"jsonrpc": "2.0", "id": 3, "method": "ping"}),
        ],
    )
    # Only the request with an id produced output.
    assert responses == [{"jsonrpc": "2.0", "id": 3, "result": {}}]


def test_command_unknown_user_errors(db):
    with pytest.raises(CommandError):
        call_command("mcp_stdio", "--user", "ghost", stdin=StringIO(""), stdout=StringIO())


def test_command_requires_user(db):
    with pytest.raises(CommandError):
        call_command("mcp_stdio", stdin=StringIO(""), stdout=StringIO())
