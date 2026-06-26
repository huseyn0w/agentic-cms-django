"""Media library services — data access and upload preparation for media views.

Keeps the media views at the HTTP boundary. File metadata and thumbnail
generation already live in ``MediaAsset.save()`` and file cleanup in a
``post_delete`` signal; this module owns only the view-facing data access.
"""

from __future__ import annotations

from django.db.models import QuerySet
from django.template.defaultfilters import filesizeformat

from .constants import ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE
from .models import MediaAsset
from .repositories import MediaRepository


def list_assets() -> QuerySet:
    """All media assets for the library grid, newest first (uploader prefetched)."""
    return MediaRepository.all()


def prepare_upload(asset: MediaAsset, user) -> None:
    """Stamp the uploader on a new asset before the form persists it."""
    asset.uploaded_by = user


def upload_constraints() -> dict:
    """Human-readable upload limits for the upload form (allowed types, max size)."""
    return {
        "allowed_types": ", ".join(e.upper() for e in sorted(ALLOWED_EXTENSIONS)),
        "max_size": filesizeformat(MAX_UPLOAD_SIZE),
    }
