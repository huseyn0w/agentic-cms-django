"""Fixtures + auto-marking for the Playwright end-to-end suite.

Every test in this directory drives a real headless Chromium against a live
Django server (`live_server`) serving the built frontend bundle. They are slow
and need a browser, so they are auto-marked `e2e` and excluded from the default
`pytest` run — invoke explicitly:

    pytest tests/e2e -m e2e --ds=config.settings.test_e2e
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from apps.content.models import Post, Status

User = get_user_model()


def pytest_collection_modifyitems(items):
    """Mark tests under tests/e2e/ as `e2e` so the default run skips them.

    The hook is global (it receives the whole session's items), so it must filter
    to this directory rather than marking everything.
    """
    here = Path(__file__).parent
    for item in items:
        if here in Path(str(item.path)).parents or Path(str(item.path)).parent == here:
            item.add_marker(pytest.mark.e2e)


@pytest.fixture
def author(db):
    return User.objects.create_user(
        username="ada", email="ada@example.com", password="pw", first_name="Ada"
    )


@pytest.fixture
def published_post(db, author):
    """A live post with a findable title + body, visible to the live server."""
    return Post.objects.create(
        title="Hello E2E World",
        body="<p>A complete journey through the published article body.</p>",
        excerpt="A complete journey.",
        status=Status.PUBLISHED,
        author=author,
    )


@pytest.fixture
def admin_user(db):
    user = User.objects.create_user(
        username="boss", email="boss@example.com", password="pw-secret-123"
    )
    user.groups.add(Group.objects.get(name="Administrator"))
    return user


@pytest.fixture
def png_upload():
    """A small in-memory PNG as a Playwright file payload for upload journeys."""
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), color=(80, 120, 200)).save(buffer, format="PNG")
    return {
        "name": "e2e-upload.png",
        "mimeType": "image/png",
        "buffer": buffer.getvalue(),
    }


def login(page, live_server, username, password):
    """Sign in through the real allauth form (shared by admin journeys)."""
    page.goto(f"{live_server.url}/accounts/login/")
    page.locator("input[name='login']").fill(username)
    page.locator("input[name='password']").fill(password)
    page.locator("button[type='submit']").first.click()
