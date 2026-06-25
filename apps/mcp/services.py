"""MCP execution service: list tools and dispatch calls with auth re-checks."""

from __future__ import annotations

from .tools import TOOLS, TOOLS_BY_NAME


class ToolError(Exception):
    """A tool call that failed for a client-facing reason (mapped to an HTTP code)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def list_tools() -> list[dict]:
    return [tool.schema() for tool in TOOLS]


def call_tool(user, name: str, arguments: dict | None) -> dict:
    tool = TOOLS_BY_NAME.get(name)
    if tool is None:
        raise ToolError("unknown_tool", f"No tool named {name!r}.")
    missing = [perm for perm in tool.permissions if not user.has_perm(perm)]
    if missing:
        raise ToolError("forbidden", f"Missing permission(s): {', '.join(missing)}.")
    try:
        return tool.handler(user, arguments or {})
    except KeyError as exc:
        raise ToolError("invalid_arguments", f"Missing argument: {exc}.") from exc
