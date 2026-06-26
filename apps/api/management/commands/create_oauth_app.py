"""Mint a local OAuth 2.1 Application (client) for testing/dev.

    python manage.py create_oauth_app --name "Local MCP client" --user <username>

Prints the client_id and the (one-time) plaintext client_secret. By default it
creates a confidential client using the authorization-code grant; PKCE is
enforced project-wide (OAUTH2_PROVIDER["PKCE_REQUIRED"]). Pass ``--public`` for
a public client (no usable secret). Use ``--redirect-uri`` to set the callback.

Run the authorization-code + PKCE flow against ``/oauth/authorize/`` and exchange
the code at ``/oauth/token/``; send the resulting token as
``Authorization: Bearer <access_token>`` to the API and MCP endpoints.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.api import services


class Command(BaseCommand):
    help = "Create a local OAuth Application (client) for the API/MCP."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--name", default="Local OAuth client")
        parser.add_argument(
            "--user",
            default=None,
            help="Username to own the Application (optional).",
        )
        parser.add_argument(
            "--redirect-uri",
            default="http://localhost:8000/noop/",
            help="Allowed redirect URI for the authorization-code flow.",
        )
        parser.add_argument(
            "--public",
            action="store_true",
            help="Create a public client (PKCE, no usable secret) instead of confidential.",
        )

    def handle(self, *args, **options) -> None:
        try:
            result = services.create_oauth_application(
                name=options["name"],
                username=options["user"],
                redirect_uri=options["redirect_uri"],
                public=options["public"],
            )
        except LookupError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(f"client_id:     {result['client_id']}")
        self.stdout.write(f"client_secret: {result['client_secret']}")
        self.stdout.write(f"client_type:   {result['client_type']}")
        self.stdout.write(f"grant_type:    {result['authorization_grant_type']}")
        self.stdout.write(
            "Store the client_secret now — it is not retrievable later (it is hashed)."
        )
