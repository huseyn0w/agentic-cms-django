import pytest
from django.contrib.auth import get_user_model

from apps.media.services import prepare_upload, upload_constraints

User = get_user_model()
pytestmark = pytest.mark.django_db


def test_prepare_upload_stamps_uploader():
    user = User.objects.create_user(username="u", email="u@example.com")

    class _Asset:
        uploaded_by = None

    asset = _Asset()
    prepare_upload(asset, user)
    assert asset.uploaded_by == user


def test_upload_constraints_lists_types_and_size():
    c = upload_constraints()
    assert "allowed_types" in c and c["allowed_types"]
    assert "max_size" in c and c["max_size"]
