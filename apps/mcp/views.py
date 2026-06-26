"""MCP HTTP endpoint — a JSON-RPC-style ``tools/list`` + ``tools/call`` surface.

Token (or session) authentication is the auth floor; every tool then re-verifies
its own permissions in the service. The view is a thin boundary that maps tool
outcomes to HTTP status codes.
"""

from __future__ import annotations

import json

from django.http import StreamingHttpResponse
from oauth2_provider.contrib.rest_framework import OAuth2Authentication
from rest_framework import status
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .services import ToolError

_ERROR_STATUS = {"unknown_tool": 404, "forbidden": 403, "invalid_arguments": 400}

# Auth floor for every MCP transport: token (programmatic), session (dashboard),
# and OAuth2 Bearer (OAuth 2.1). Authorization is still enforced per tool in
# ``services.call_tool``; OAuth only authenticates the caller.
MCP_AUTHENTICATION_CLASSES = [
    TokenAuthentication,
    SessionAuthentication,
    OAuth2Authentication,
]


def _token_scopes(request) -> set[str] | None:
    """Scopes carried by an OAuth Bearer token, or ``None`` for Token/Session auth.

    Returns ``None`` only for non-OAuth auth (Token/Session), which is not scoped,
    so the scope gate is skipped for those. For an OAuth Bearer token it always
    returns the scope SET — possibly empty — so an empty-scope token is still
    gated (it lacks ``write`` and so cannot run write tools).
    """
    if not isinstance(request.successful_authenticator, OAuth2Authentication):
        return None
    scope = getattr(request.auth, "scope", "") or ""
    return set(scope.split())


class MCPView(APIView):
    authentication_classes = MCP_AUTHENTICATION_CLASSES
    permission_classes = [IsAuthenticated]

    def post(self, request):
        method = request.data.get("method")
        if method == "tools/list":
            return Response({"result": {"tools": services.list_tools()}})
        if method == "tools/call":
            params = request.data.get("params") or {}
            try:
                result = services.call_tool(
                    request.user,
                    params.get("name"),
                    params.get("arguments"),
                    _token_scopes(request),
                )
            except ToolError as exc:
                return Response(
                    {"error": {"code": exc.code, "message": exc.message}},
                    status=_ERROR_STATUS.get(exc.code, 400),
                )
            return Response({"result": result})
        return Response(
            {"error": {"code": "unknown_method", "message": "Use tools/list or tools/call."}},
            status=status.HTTP_400_BAD_REQUEST,
        )


class MCPSSEView(APIView):
    """Streaming (SSE) MCP transport.

    Same auth floor as the JSON endpoint; the HTTP boundary only — it delegates
    to ``services.stream_events``, which reuses the tool registry and the same
    per-tool authorization. On connect it streams a ``tools/list`` event; pass
    ``?name=<tool>&arguments=<json>`` to also stream a ``tools/call`` result.
    """

    authentication_classes = MCP_AUTHENTICATION_CLASSES
    permission_classes = [IsAuthenticated]

    def get(self, request):
        name = request.query_params.get("name") or None
        arguments = self._parse_arguments(request.query_params.get("arguments"))
        response = StreamingHttpResponse(
            services.stream_events(request.user, name, arguments, _token_scopes(request)),
            content_type="text/event-stream",
        )
        # Disable proxy buffering so events flush as they are produced.
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response

    @staticmethod
    def _parse_arguments(raw: str | None) -> dict:
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
