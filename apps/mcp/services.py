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
    name: str | None,
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
    tool = TOOLS_BY_NAME.get(name) if name is not None else None
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


# --------------------------------------------------------------------------- #
# JSON-RPC 2.0 dispatch — shared by the stdio transport (and unit-testable
# without any I/O). The transport (the management command) only reads stdin and
# writes stdout; this function turns one request dict into one response dict.
# --------------------------------------------------------------------------- #
# Minimal server identity returned by ``initialize``.
SERVER_INFO = {"name": "agentic-cms-mcp", "version": "1.0.0"}
PROTOCOL_VERSION = "2024-11-05"

# JSON-RPC error codes (subset we use).
_PARSE_ERROR = -32700
_METHOD_NOT_FOUND = -32601

# Map ToolError codes to JSON-RPC error codes for tools/call failures.
_TOOL_ERROR_RPC_CODE = {
    "unknown_tool": -32602,
    "forbidden": -32000,
    "invalid_arguments": -32602,
}


def _rpc_result(request_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _rpc_error(request_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle_jsonrpc(user, request: dict) -> dict | None:
    """Dispatch one JSON-RPC 2.0 request for ``user``; return the response dict.

    Returns ``None`` for a notification (a request without an ``id``), per the
    JSON-RPC spec. ``tools/call`` runs through ``call_tool`` with NO scope gate
    (stdio has no bearer token — authorization is the resolved user's Django
    permissions, re-verified per tool). A ``ToolError`` becomes a JSON-RPC error
    object rather than an exception.
    """
    request_id = request.get("id")
    is_notification = "id" not in request
    method = request.get("method")

    if method == "initialize":
        result: dict = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": list_tools()}
    elif method == "tools/call":
        params = request.get("params") or {}
        try:
            tool_result = call_tool(user, params.get("name"), params.get("arguments"))
        except ToolError as exc:
            if is_notification:
                return None
            return _rpc_error(request_id, _TOOL_ERROR_RPC_CODE.get(exc.code, -32603), exc.message)
        result = {"content": tool_result}
    else:
        if is_notification:
            return None
        return _rpc_error(request_id, _METHOD_NOT_FOUND, f"Unknown method: {method!r}.")

    if is_notification:
        return None
    return _rpc_result(request_id, result)


def parse_error_response() -> dict:
    """A JSON-RPC parse-error response (for a malformed input line)."""
    return _rpc_error(None, _PARSE_ERROR, "Parse error: invalid JSON.")


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
