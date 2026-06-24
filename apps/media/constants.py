"""Upload constraints for the media library.

SVG is intentionally excluded: SVG files can carry embedded scripts and, when
served inline, become a stored-XSS vector. Many popular CMSs restrict SVG by
default for the same reason. Keep this list conservative.
"""

# Lower-case extensions without the dot.
ALLOWED_EXTENSIONS: set[str] = {"jpg", "jpeg", "png", "gif", "webp", "pdf"}

# Extensions we can rasterize into a thumbnail with Pillow.
RASTER_IMAGE_EXTENSIONS: set[str] = {"jpg", "jpeg", "png", "gif", "webp"}

MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10 MB

THUMBNAIL_SIZE: tuple[int, int] = (400, 400)
