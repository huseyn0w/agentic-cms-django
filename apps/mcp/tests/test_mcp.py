"""MCP endpoint: auth floor + per-tool authorization (F12c)."""

import json

import pytest

from apps.comments.models import Comment, CommentStatus
from apps.content.models import Post, Status

pytestmark = pytest.mark.django_db

URL = "/api/mcp/"


def _rpc(client, payload, **extra):
    return client.post(URL, data=json.dumps(payload), content_type="application/json", **extra)


def test_requires_authentication(client):
    response = _rpc(client, {"method": "tools/list"})
    assert response.status_code in (401, 403)


def test_tools_list(client, make_user, auth_headers):
    editor = make_user("ed", role="Editor")
    data = _rpc(client, {"method": "tools/list"}, **auth_headers(editor)).json()
    names = {t["name"] for t in data["result"]["tools"]}
    assert {"posts.create", "posts.publish", "comments.moderate", "users.list"} <= names


def test_create_post_tool(client, make_user, auth_headers):
    author = make_user("a", role="Author")
    data = _rpc(
        client,
        {
            "method": "tools/call",
            "params": {"name": "posts.create", "arguments": {"title": "Via MCP"}},
        },
        **auth_headers(author),
    ).json()
    assert data["result"]["title"] == "Via MCP"
    assert Post.objects.get().author == author


def test_tool_forbidden_without_permission(client, make_user, auth_headers):
    subscriber = make_user("sub", role="Subscriber")  # no content perms
    response = _rpc(
        client,
        {"method": "tools/call", "params": {"name": "posts.create", "arguments": {"title": "X"}}},
        **auth_headers(subscriber),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert Post.objects.count() == 0


def test_publish_tool_requires_publish_permission(client, make_user, auth_headers):
    contributor = make_user("c", role="Contributor")  # no publish_post, no delete
    post = Post.objects.create(title="Draft", author=contributor)
    response = _rpc(
        client,
        {"method": "tools/call", "params": {"name": "posts.publish", "arguments": {"id": post.pk}}},
        **auth_headers(contributor),
    )
    assert response.status_code == 403


def test_moderate_comment_tool(client, make_user, auth_headers):
    editor = make_user("ed", role="Editor")
    post = Post.objects.create(title="P", author=editor, status=Status.PUBLISHED)
    comment = Comment.objects.create(post=post, name="Guest", body="hi")
    _rpc(
        client,
        {
            "method": "tools/call",
            "params": {
                "name": "comments.moderate",
                "arguments": {"id": comment.pk, "action": "approve"},
            },
        },
        **auth_headers(editor),
    )
    comment.refresh_from_db()
    assert comment.status == CommentStatus.APPROVED


def test_unknown_tool_is_404(client, make_user, auth_headers):
    editor = make_user("ed", role="Editor")
    response = _rpc(
        client,
        {"method": "tools/call", "params": {"name": "nope.nope", "arguments": {}}},
        **auth_headers(editor),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "unknown_tool"


def test_unknown_method_is_400(client, make_user, auth_headers):
    editor = make_user("ed", role="Editor")
    response = _rpc(client, {"method": "bogus"}, **auth_headers(editor))
    assert response.status_code == 400


def _call(client, headers, name, arguments=None):
    return _rpc(
        client,
        {"method": "tools/call", "params": {"name": name, "arguments": arguments or {}}},
        **headers,
    )


@pytest.mark.parametrize(
    "tool,key",
    [
        ("posts.list", "posts"),
        ("pages.list", "pages"),
        ("categories.list", "categories"),
        ("tags.list", "tags"),
        ("media.list", "media"),
        ("users.list", "users"),
        ("settings.get", "site_name"),
    ],
)
def test_read_tools_return_payload(client, make_user, auth_headers, tool, key):
    boss = make_user("boss", role="Administrator")
    headers = auth_headers(boss)
    Post.objects.create(title="P", author=boss, status=Status.PUBLISHED)
    data = _call(client, headers, tool).json()
    assert key in data["result"]


def test_get_update_delete_post_tools(client, make_user, auth_headers):
    boss = make_user("boss", role="Administrator")
    headers = auth_headers(boss)
    post = Post.objects.create(title="Orig", body="<p>x</p>", author=boss)

    got = _call(client, headers, "posts.get", {"id": post.pk}).json()
    assert got["result"]["body"] == "<p>x</p>"

    _call(client, headers, "posts.update", {"id": post.pk, "title": "Renamed"})
    post.refresh_from_db()
    assert post.safe_translation_getter("title") == "Renamed"

    _call(client, headers, "posts.delete", {"id": post.pk})
    assert Post.objects.only_trashed().filter(pk=post.pk).exists()


def test_publish_post_tool_success(client, make_user, auth_headers):
    author = make_user("a", role="Author")  # has publish_post
    post = Post.objects.create(title="Draft", author=author)
    _call(client, auth_headers(author), "posts.publish", {"id": post.pk})
    post.refresh_from_db()
    assert post.status == Status.PUBLISHED


def test_missing_argument_is_400(client, make_user, auth_headers):
    boss = make_user("boss", role="Administrator")
    response = _call(client, auth_headers(boss), "posts.get")  # no id
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_arguments"
