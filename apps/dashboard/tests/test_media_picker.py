"""In-editor media picker (F11): visibility + image-only listing."""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from apps.dashboard import services
from apps.media.models import MediaAsset

pytestmark = pytest.mark.django_db

_PICKER_LABEL = b"Insert image from library"


def _png(name="pic.png"):
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), "red").save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


def test_picker_shown_to_user_with_media_access(client, make_user):
    author = make_user("a", role="Author")  # Author has media.view_mediaasset
    MediaAsset.objects.create(file=_png(), uploaded_by=author, alt_text="A red square")
    client.force_login(author)
    response = client.get(reverse("dashboard:post_create"))
    assert response.status_code == 200
    assert _PICKER_LABEL in response.content


def test_picker_hidden_without_media_access(client, make_user):
    contributor = make_user("c", role="Contributor")  # no media perms
    MediaAsset.objects.create(file=_png())
    client.force_login(contributor)
    response = client.get(reverse("dashboard:post_create"))
    assert response.status_code == 200
    assert _PICKER_LABEL not in response.content


def test_recent_media_images_lists_only_images(make_user):
    MediaAsset.objects.create(file=_png("image.png"))
    MediaAsset.objects.create(
        file=SimpleUploadedFile("notes.pdf", b"%PDF-1.4 x", content_type="application/pdf")
    )
    images = list(services.recent_media_images())
    assert len(images) == 1
    assert images[0].is_image
