"""Magic-byte upload validation + SVG/polyglot rejection (§7, §21).

Target (copied from agentic-cms-ts's `media.service.ts`): validate the file BYTES,
not the client-supplied extension/MIME; derive the stored extension from the
validated MIME (anti-polyglot); reject SVG.
"""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.media.forms import MediaUploadForm

pytestmark = pytest.mark.django_db


def _png_bytes(size=(40, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


def _pdf_bytes() -> bytes:
    # Minimal but structurally-valid-enough PDF (magic header is what we sniff).
    return b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


def test_png_renamed_to_jpg_is_accepted_and_extension_corrected():
    # A real PNG uploaded as ".jpg": the bytes are valid, so it's accepted, but the
    # stored file's extension is corrected to match the validated MIME (.png).
    upload = SimpleUploadedFile("photo.jpg", _png_bytes(), content_type="image/jpeg")
    form = MediaUploadForm(files={"file": upload})
    assert form.is_valid(), form.errors
    cleaned = form.cleaned_data["file"]
    assert cleaned.name.lower().endswith(".png")


def test_svg_is_rejected():
    svg = SimpleUploadedFile(
        "logo.svg",
        b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"></svg>',
        content_type="image/svg+xml",
    )
    form = MediaUploadForm(files={"file": svg})
    assert not form.is_valid()
    assert "file" in form.errors


def test_svg_renamed_to_png_is_rejected():
    # A script-carrying SVG renamed to .png must NOT sneak past extension checks:
    # byte sniffing catches that the bytes are not a real raster image.
    svg = SimpleUploadedFile(
        "sneaky.png",
        b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        content_type="image/png",
    )
    form = MediaUploadForm(files={"file": svg})
    assert not form.is_valid()
    assert "file" in form.errors


def test_script_polyglot_named_png_is_rejected():
    # An HTML/JS polyglot with a .png name — no valid image magic bytes → rejected.
    polyglot = SimpleUploadedFile(
        "polyglot.png",
        b"<html><script>alert('xss')</script></html>",
        content_type="image/png",
    )
    form = MediaUploadForm(files={"file": polyglot})
    assert not form.is_valid()
    assert "file" in form.errors


def test_gif_polyglot_with_trailing_script_is_stored_with_gif_extension():
    # A genuine GIF whose tail also contains markup: the bytes ARE a valid GIF, so
    # it's accepted, but stored as .gif (never as an executable extension), so it
    # can't be served as text/html — the anti-polyglot guarantee.
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), (0, 0, 0)).save(buf, format="GIF")
    payload = buf.getvalue() + b"<script>alert(1)</script>"
    upload = SimpleUploadedFile("evil.php", payload, content_type="image/gif")
    form = MediaUploadForm(files={"file": upload})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["file"].name.lower().endswith(".gif")


def test_valid_pdf_is_accepted():
    upload = SimpleUploadedFile("doc.pdf", _pdf_bytes(), content_type="application/pdf")
    form = MediaUploadForm(files={"file": upload})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["file"].name.lower().endswith(".pdf")


def test_fake_pdf_is_rejected():
    upload = SimpleUploadedFile("doc.pdf", b"not a pdf at all", content_type="application/pdf")
    form = MediaUploadForm(files={"file": upload})
    assert not form.is_valid()
    assert "file" in form.errors
