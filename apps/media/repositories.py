"""Media data-access layer (repository).

The single home for media ORM access used by the media services. File metadata and
thumbnails are generated in ``MediaAsset.save()`` and file cleanup in a
``post_delete`` signal — out of scope here; this repository owns queries only.
"""

from __future__ import annotations

from django.db.models import QuerySet

from .models import MediaAsset


class MediaRepository:
    @staticmethod
    def all() -> QuerySet:
        """All assets for the library grid, with uploader prefetched."""
        return MediaAsset.objects.select_related("uploaded_by")

    @staticmethod
    def count_all() -> int:
        return MediaAsset.objects.count()

    @staticmethod
    def images(limit: int) -> QuerySet:
        """Most-recent image assets for the in-editor media picker, capped."""
        return MediaAsset.objects.filter(mime_type__startswith="image/")[:limit]
