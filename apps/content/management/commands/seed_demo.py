"""Seed idempotent demo content so the public site has something to render.

Mirrors the canonical demo set every cmstack stack seeds: 3 categories, 6
published posts (one per category mapping), and About + Contact pages — each
written in ALL configured locales (en, de, ru). The trilingual copy lives in the
sibling ``demo_content.json`` (framework-neutral, ``Cmstack`` as the product).

Safe to run repeatedly: everything is keyed by ``slug`` (shared, non-translated)
and every locale's translation row is refreshed on each run, so re-running never
duplicates and always brings all three languages up to date.

    python manage.py seed_demo

Wired into ``make seed`` / ``make dev`` so content appears from a fresh boot.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.content.models import Category, Page, Post, Status

# Trilingual demo copy bundled next to this command (en/de/ru per record).
DATA_FILE = Path(__file__).with_name("demo_content.json")


def _load_data() -> dict[str, Any]:
    with DATA_FILE.open(encoding="utf-8") as fh:
        return json.load(fh)


class Command(BaseCommand):
    help = (
        "Seed idempotent, trilingual (en/de/ru) demo content: "
        "3 categories, 6 published posts, About + Contact pages."
    )

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        data = _load_data()
        # Locales to write per record. Fall back to the file's own list if a
        # deployment narrows LANGUAGES; only write locales the data provides.
        self.locales: list[str] = list(data.get("locales", ["en"]))

        author = self._get_admin()

        cats = self._seed_categories(data["categories"])
        self._seed_posts(data["posts"], author, cats)
        self._seed_pages(data["pages"], author)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {Category.objects.count()} categories, "
                f"{Post.objects.count()} posts, {Page.objects.count()} pages "
                f"in {len(self.locales)} locales ({', '.join(self.locales)})."
            )
        )

    def _get_admin(self):
        """The author for seeded content: the first superuser (created by `make superuser`)."""
        user_model = get_user_model()
        author = user_model.objects.filter(is_superuser=True).order_by("pk").first()
        if author is None:
            author = user_model.objects.order_by("pk").first()
        return author

    @staticmethod
    def _fetch_or_new(model, slug: str):
        """Fetch by slug, or build a fresh (unsaved) instance.

        We can't use ``get_or_create`` here: parler's create path calls ``save()``,
        which reads translated fields (``body``/``title``) before we've set the
        active language — raising ``DoesNotExist``. So we set each language and its
        translated fields ourselves, then save once per language.
        """
        obj = model.objects.filter(slug=slug).first()
        return obj if obj is not None else model(slug=slug)

    def _seed_categories(self, categories: list[dict[str, Any]]) -> dict[str, Category]:
        result: dict[str, Category] = {}
        for data in categories:
            category = self._fetch_or_new(Category, data["slug"])
            for code in self.locales:
                category.set_current_language(code)
                category.name = data["name"][code]
                category.description = data["description"][code]
                # save() per language so each translation row is written; the slug
                # (shared) is set once on the first save.
                category.save()
            result[data["slug"]] = category
        return result

    def _seed_posts(self, posts: list[dict[str, Any]], author, cats: dict[str, Category]) -> None:
        now = timezone.now()
        for data in posts:
            post = self._fetch_or_new(Post, data["slug"])
            post.status = Status.PUBLISHED
            post.author = author
            # Ensure it is publicly visible: published() filters on
            # status=PUBLISHED AND published_at <= now. save() only stamps this on
            # the first publish, so set it explicitly for idempotent re-runs.
            if post.published_at is None:
                post.published_at = now
            for code in self.locales:
                post.set_current_language(code)
                post.title = data["title"][code]
                post.excerpt = data["excerpt"][code]
                post.body = data["content"][code]
                post.save()
            post.categories.set([cats[data["categorySlug"]]])

    def _seed_pages(self, pages: list[dict[str, Any]], author) -> None:
        now = timezone.now()
        for data in pages:
            page = self._fetch_or_new(Page, data["slug"])
            page.status = Status.PUBLISHED
            page.author = author
            if page.published_at is None:
                page.published_at = now
            for code in self.locales:
                page.set_current_language(code)
                page.title = data["title"][code]
                page.body = data["content"][code]
                page.save()
