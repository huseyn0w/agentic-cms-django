"""Settings for the Playwright end-to-end suite.

Identical to the SQLite ``test`` settings, but with Vite in *built* mode so the
``live_server`` static handler serves the real bundled CSS/JS from
``frontend/dist`` (the manifest must exist — run ``cd frontend && npm run build``
first). The default ``test`` settings render Vite dev-server URLs, which a
headless browser cannot load. Select it with
``pytest tests/e2e -m e2e --ds=config.settings.test_e2e``.
"""

import os

from .test import *  # noqa: F401,F403,E402

# pytest-playwright's sync API runs the test under a live asyncio event loop, so
# Django's "synchronous-only" guard would otherwise reject the ORM calls that the
# fixtures and live_server make. The DB access is genuinely on a worker thread, so
# allowing it here is safe and scoped to the E2E settings only.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

# Serve the built bundle (frontend/dist) through django-vite's manifest instead
# of dev-server URLs, so the browser gets working Alpine/Tailwind assets.
DJANGO_VITE["default"]["dev_mode"] = False  # noqa: F405
