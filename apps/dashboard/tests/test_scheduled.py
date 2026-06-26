"""Dashboard scheduling UI (F8): publishers can set a future publish time."""

import pytest
from django.urls import reverse

from apps.content.models import Post, Status

pytestmark = pytest.mark.django_db


def test_publisher_can_schedule_a_post(client, make_user):
    editor = make_user("ed", role="Editor")
    client.force_login(editor)
    response = client.post(
        reverse("dashboard:post_create"),
        {
            "title": "Scheduled",
            "slug": "",
            "excerpt": "",
            "body": "<p>x</p>",
            "status": "draft",
            "scheduled_at": "2099-01-01T09:00",
        },
    )
    assert response.status_code == 302
    post = Post.objects.get()
    assert post.status == Status.DRAFT
    assert post.scheduled_at is not None
    assert post.scheduled_at.year == 2099


def test_contributor_form_has_no_schedule_field(client, make_user):
    client.force_login(make_user("c", role="Contributor"))
    response = client.get(reverse("dashboard:post_create"))
    assert response.status_code == 200
    assert b'name="scheduled_at"' not in response.content
