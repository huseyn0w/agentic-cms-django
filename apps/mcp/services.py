"""MCP execution service: list tools and dispatch calls with auth re-checks."""

from __future__ import annotations

import json
from collections.abc import Iterator

from .tools import TOOLS, TOOLS_BY_NAME


class ToolError(Exception):
    """A tool call that failed for a client-facing reason (mapped to an HTTP code)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def list_tools() -> list[dict]:
    return [tool.schema() for tool in TOOLS]


def call_tool(
    user,
    name: str,
    arguments: dict | None,
    token_scopes: set[str] | None = None,
) -> dict:
    """Run a tool after re-verifying its permissions (and, for OAuth, its scope).

    ``token_scopes`` is the set of scopes carried by an OAuth Bearer token, or
    ``None`` for Token/Session auth (which is not OAuth-scoped). When it is not
    ``None``, a state-mutating tool (``tool.write``) additionally requires the
    ``write`` scope — an ADDITIONAL gate on top of the per-tool model permission,
    so a ``read``-scope (or empty-scope) token can't run write tools. Token/Session
    callers (``token_scopes is None``) skip the scope gate entirely.
    """
    tool = TOOLS_BY_NAME.get(name)
    if tool is None:
        raise ToolError("unknown_tool", f"No tool named {name!r}.")
    if token_scopes is not None and tool.write and "write" not in token_scopes:
        raise ToolError("forbidden", "This tool requires the 'write' OAuth scope.")
    missing = [perm for perm in tool.permissions if not user.has_perm(perm)]
    if missing:
        raise ToolError("forbidden", f"Missing permission(s): {', '.join(missing)}.")
    try:
        return tool.handler(user, arguments or {})
    except KeyError as exc:
        raise ToolError("invalid_arguments", f"Missing argument: {exc}.") from exc


def _sse_event(event: str, data: dict) -> str:
    """Format one Server-Sent Event (an ``event:`` line + a JSON ``data:`` line)."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def stream_events(
    user,
    name: str | None = None,
    arguments: dict | None = None,
    token_scopes: set[str] | None = None,
) -> Iterator[str]:
    """Yield MCP-style SSE events for a streaming connection.

    Always emits an initial ``tools/list`` event so a client can discover the
    surface on connect. If ``name`` is given, the tool is executed (with the same
    per-tool authorization AND OAuth scope gate as the JSON endpoint) and its
    result is streamed as a ``tools/call`` event — or, on failure, an ``error``
    event. ``token_scopes`` follows the same contract as ``call_tool``.
    """
    yield _sse_event("tools/list", {"tools": list_tools()})
    if name:
        try:
            result = call_tool(user, name, arguments, token_scopes)
        except ToolError as exc:
            yield _sse_event("error", {"code": exc.code, "message": exc.message})
        else:
            yield _sse_event("tools/call", {"name": name, "result": result})
