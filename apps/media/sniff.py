"""Byte-level ("magic byte") upload validation for the media library.

The extension a browser sends is attacker-controlled, so it is NOT trusted for
type decisions. This module inspects the file's actual bytes to determine its
real type, then the form derives the STORED extension from that validated type —
never from the user-supplied filename. This is the anti-polyglot guarantee ported
from agentic-cms-ts's ``media.service.ts``: a file whose bytes are a valid GIF but
which is named ``evil.php`` is stored as ``.gif`` and can never be served as
executable/text-html content.

Approach (no heavy new deps — Pillow is already a requirement):

- Raster images (jpg/png/gif/webp): sniffed and structurally verified with Pillow
  (``Image.open(...).verify()``), so a mislabelled or corrupt file is rejected.
- PDF: the ``%PDF-`` magic header is checked directly.
- SVG (and any non-image XML/HTML/script polyglot): has no valid raster/PDF magic,
  so it fails validation and is rejected — SVG can carry inline script and is an
  XSS vector when served inline.
"""

from __future__ import annotations

from PIL import Image

# Validated MIME -> the single canonical stored extension (with dot). The stored
# extension is ALWAYS one of these, derived from the sniffed bytes.
EXTENSION_FOR_MIME: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}

# Pillow's format string -> our canonical MIME (image branch only).
_MIME_FOR_PIL_FORMAT: dict[str, str] = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "GIF": "image/gif",
    "WEBP": "image/webp",
}

_PDF_MAGIC = b"%PDF-"


class UnsupportedUpload(Exception):
    """Raised when the file's actual bytes are not an allowed, valid type."""


def _read_head(uploaded, n: int = 4096) -> bytes:
    """Read the first ``n`` bytes without consuming the upload's file pointer."""
    uploaded.seek(0)
    head = uploaded.read(n)
    uploaded.seek(0)
    return head


def sniff_mime(uploaded) -> str:
    """Return the validated MIME of ``uploaded`` from its bytes, or raise.

    Only jpg/png/gif/webp/pdf validate; everything else (SVG, HTML/JS polyglots,
    renamed scripts, corrupt images) raises :class:`UnsupportedUpload`.
    """
    head = _read_head(uploaded)

    if head.startswith(_PDF_MAGIC):
        return "application/pdf"

    # Structurally verify raster images with Pillow. verify() parses the file
    # enough to catch a non-image/corrupt payload; it must run on a fresh handle.
    try:
        uploaded.seek(0)
        with Image.open(uploaded) as image:
            image.verify()
            fmt = (image.format or "").upper()
    except Exception as exc:  # noqa: BLE001 — any decode failure = not a valid image
        raise UnsupportedUpload("The uploaded file is not a valid image or PDF.") from exc
    finally:
        uploaded.seek(0)

    mime = _MIME_FOR_PIL_FORMAT.get(fmt)
    if mime is None:
        raise UnsupportedUpload("Unsupported image format.")
    return mime


def extension_for_mime(mime: str) -> str:
    """The canonical stored extension (with dot) for a validated MIME."""
    return EXTENSION_FOR_MIME[mime]
