"""Publish scheduled content whose time has arrived.

Run periodically from cron / a scheduler, e.g. every minute:

    * * * * * cd /app && python manage.py publish_scheduled
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.content import services


class Command(BaseCommand):
    help = "Publish draft posts/pages/services whose scheduled time has passed."

    def handle(self, *args, **options) -> None:
        counts = services.publish_scheduled_content()
        total = sum(counts.values())
        self.stdout.write(
            f"Published {total} item(s) "
            f"(posts={counts['posts']}, pages={counts['pages']}, services={counts['services']})."
        )
