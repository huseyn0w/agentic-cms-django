"""Accessibility wiring for dashboard forms and locale tabs (U6)."""

import pytest
from django.urls import reverse

from apps.content.models import Post

pytestmark = pytest.mark.django_db


def test_invalid_field_gets_aria_invalid_and_describedby(client, make_user):
    author = make_user("au", role="Author")
    client.force_login(author)
    # Empty title is invalid -> the form re-renders with field errors.
    response = client.post(
        reverse("dashboard:post_create"),
        {"title": "", "slug": "", "excerpt": "", "body": "<p>x</p>", "status": "draft"},
    )
    assert response.status_code == 200
    html = response.content.decode()
    assert 'aria-invalid="true"' in html
    # The widget points at its error container, which carries the matching id.
    assert "id_title_error" in html
    assert 'aria-describedby="id_title_error"' in html


def test_language_tabs_mark_the_current_tab(client, make_user):
    editor = make_user("ed", role="Editor")
    post = Post.objects.create(title="Tabbed", author=editor)
    client.force_login(editor)
    html = client.get(reverse("dashboard:post_edit", args=[post.pk])).content.decode()

    assert 'role="tablist"' in html
    assert 'role="tab"' in html
    assert 'aria-selected="true"' in html
    assert 'aria-current="page"' in html
