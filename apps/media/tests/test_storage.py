"""Swappable storage-driver selection (F11)."""

import environ

from config.storages import build_storages


def _env(**values):
    e = environ.Env()
    e.ENVIRON = values
    return e


def test_defaults_to_local_disk():
    storages = build_storages(_env())
    assert storages["default"]["BACKEND"] == "django.core.files.storage.FileSystemStorage"
    assert "whitenoise" in storages["staticfiles"]["BACKEND"]


def test_switches_to_s3_when_enabled():
    storages = build_storages(
        _env(
            USE_S3_MEDIA="1",
            AWS_STORAGE_BUCKET_NAME="my-bucket",
            AWS_S3_REGION_NAME="eu-central-1",
        )
    )
    default = storages["default"]
    assert default["BACKEND"] == "storages.backends.s3.S3Storage"
    assert default["OPTIONS"]["bucket_name"] == "my-bucket"
    assert default["OPTIONS"]["region_name"] == "eu-central-1"
    assert default["OPTIONS"]["file_overwrite"] is False


def test_s3_optional_endpoint_and_domain_default_to_none():
    storages = build_storages(_env(USE_S3_MEDIA="true"))
    opts = storages["default"]["OPTIONS"]
    assert opts["endpoint_url"] is None
    assert opts["custom_domain"] is None
