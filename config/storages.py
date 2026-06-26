"""Swappable file-storage configuration (Django 5 ``STORAGES``).

The storage backend is the one Strategy point where a real swap pays off: local
disk in dev, an S3-compatible object store in prod. ``FileField``/``ImageField``
(media library, avatars, OG/featured images) all use the ``default`` storage, so
flipping ``USE_S3_MEDIA=1`` moves every upload to S3 with no model changes.

Kept as a pure ``build_storages(env)`` function so the selection logic is unit-
testable without importing boto3 / instantiating a backend.
"""

from __future__ import annotations

_STATIC_BACKEND = {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}
_LOCAL_BACKEND = {"BACKEND": "django.core.files.storage.FileSystemStorage"}


def _s3_backend(env) -> dict:
    """S3 (or S3-compatible, e.g. MinIO/R2) backend config from env."""
    return {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": env.str("AWS_STORAGE_BUCKET_NAME", default=""),
            "region_name": env.str("AWS_S3_REGION_NAME", default=""),
            # endpoint_url lets non-AWS providers (MinIO/R2) work; blank → AWS.
            "endpoint_url": env.str("AWS_S3_ENDPOINT_URL", default="") or None,
            # Serve via a CDN/custom domain when set; else the bucket URL.
            "custom_domain": env.str("AWS_S3_CUSTOM_DOMAIN", default="") or None,
            # Public-read media → no signed querystrings; never clobber on collision.
            "querystring_auth": env.bool("AWS_S3_QUERYSTRING_AUTH", default=False),
            "file_overwrite": False,
        },
    }


def build_storages(env) -> dict:
    """Return the ``STORAGES`` mapping for the current environment.

    ``staticfiles`` is always WhiteNoise; ``default`` is S3 when ``USE_S3_MEDIA``
    is truthy, otherwise local disk.
    """
    default_backend = (
        _s3_backend(env) if env.bool("USE_S3_MEDIA", default=False) else _LOCAL_BACKEND
    )
    return {"default": default_backend, "staticfiles": _STATIC_BACKEND}
