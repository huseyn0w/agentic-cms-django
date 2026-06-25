"""MCP HTTP endpoint — a JSON-RPC-style ``tools/list`` + ``tools/call`` surface.

Token (or session) authentication is the auth floor; every tool then re-verifies
its own permissions in the service. The view is a thin boundary that maps tool
outcomes to HTTP status codes.
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .services import ToolError

_ERROR_STATUS = {"unknown_tool": 404, "forbidden": 403, "invalid_arguments": 400}


class MCPView(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        method = request.data.get("method")
        if method == "tools/list":
            return Response({"result": {"tools": services.list_tools()}})
        if method == "tools/call":
            params = request.data.get("params") or {}
            try:
                result = services.call_tool(
                    request.user, params.get("name"), params.get("arguments")
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
