"""Mint (or fetch) an API token for a user.

    python manage.py create_api_token <username>

Clients then send it as ``Authorization: Token <key>``.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.api import services


class Command(BaseCommand):
    help = "Create or retrieve an API auth token for a user."

    def add_arguments(self, parser) -> None:
        parser.add_argument("username")

    def handle(self, *args, **options) -> None:
        username = options["username"]
        key = services.issue_token(username)
        if key is None:
            raise CommandError(f"No user named {username!r}.")
        self.stdout.write(key)
