"""Stdio MCP transport — a local JSON-RPC 2.0 loop over stdin/stdout.

    python manage.py mcp_stdio --user <username>

Framing: line-delimited JSON ("JSON Lines"). The client writes ONE JSON-RPC 2.0
request object per line to stdin; the server writes ONE JSON response object per
line to stdout. This is the simplest framing and is what local MCP clients (e.g.
Claude Desktop, configured with a stdio command) expect for a line-based server.

Authorization: stdio has no bearer token, so there is no OAuth scope concept. The
command resolves ``--user`` up front and runs EVERY tool as that user; the
existing per-tool ``has_perm`` re-verification in ``services.call_tool`` is the
authorization (local trust + the chosen user's Django permissions). Run this as a
trusted, low-privilege user where possible.

Supported methods: ``initialize``, ``ping``, ``tools/list``, ``tools/call``.
Unknown method → JSON-RPC error -32601. A malformed input line → JSON-RPC parse
error -32700 (the loop stays alive and reads the next line). Notifications
(requests without an ``id``) produce no response line.
"""

from __future__ import annotations

import json
import sys

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.repositories import UserRepository
from apps.mcp import services


class Command(BaseCommand):
    help = "Run a local stdio MCP transport (line-delimited JSON-RPC 2.0) as a user."

    # Allow ``call_command(..., stdin=...)`` to inject a stream in tests; in real
    # use the command falls back to ``sys.stdin``.
    stealth_options = ("stdin",)

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--user",
            required=True,
            help="Username to run every tool call as (its Django permissions gate access).",
        )

    def handle(self, *args, **options) -> None:
        username = options["user"]
        user = UserRepository.get_by_username(username)
        if user is None:
            raise CommandError(f"No user named {username!r}.")

        stdin = options.get("stdin") or sys.stdin
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except (TypeError, ValueError):
                self._write(services.parse_error_response())
                continue
            if not isinstance(request, dict):
                self._write(services.parse_error_response())
                continue
            response = services.handle_jsonrpc(user, request)
            if response is not None:
                self._write(response)

    def _write(self, response: dict) -> None:
        # One compact JSON object per line (the response framing).
        self.stdout.write(json.dumps(response))
