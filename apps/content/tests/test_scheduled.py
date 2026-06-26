"""Scheduled (future) publishing (F8): model, query, service, command."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.content import services
from apps.content.models import Page, Post, Service, Status

pytestmark = pytest.mark.django_db


def _past():
    return timezone.now() - timedelta(minutes=5)


def _future():
    return timezone.now() + timedelta(days=1)


# --------------------------------------------------------------------------- #
# Model state
# --------------------------------------------------------------------------- #
def test_scheduled_draft_is_not_published_yet():
    post = Post.objects.create(title="Soon", status=Status.DRAFT, scheduled_at=_past())
    assert post.is_published is False
    assert post.is_scheduled is True
    assert post not in Post.objects.published()


def test_publish_scheduled_uses_scheduled_time_as_publish_date():
    when = _past()
    post = Post.objects.create(title="Soon", status=Status.DRAFT, scheduled_at=when)
    post.publish_scheduled()
    post.refresh_from_db()
    assert post.status == Status.PUBLISHED
    assert post.scheduled_at is None
    assert abs((post.published_at - when).total_seconds()) < 1
    assert post.is_published is True


# --------------------------------------------------------------------------- #
# due_for_publish query
# --------------------------------------------------------------------------- #
def test_due_for_publish_selects_only_due_drafts():
    due = Post.objects.create(title="Due", status=Status.DRAFT, scheduled_at=_past())
    Post.objects.create(title="Later", status=Status.DRAFT, scheduled_at=_future())
    Post.objects.create(title="Plain draft", status=Status.DRAFT)
    Post.objects.create(title="Live", status=Status.PUBLISHED)
    assert list(Post.objects.due_for_publish()) == [due]


def test_due_for_publish_excludes_trashed():
    post = Post.objects.create(title="Trashed due", status=Status.DRAFT, scheduled_at=_past())
    post.trash()
    assert list(Post.objects.due_for_publish()) == []


# --------------------------------------------------------------------------- #
# Service + management command
# --------------------------------------------------------------------------- #
def test_service_publishes_due_across_content_types():
    Post.objects.create(title="P", status=Status.DRAFT, scheduled_at=_past())
    Page.objects.create(title="Pg", status=Status.DRAFT, scheduled_at=_past())
    Service.objects.create(title="Svc", status=Status.DRAFT, scheduled_at=_past())

    counts = services.publish_scheduled_content()
    assert counts == {"posts": 1, "pages": 1, "services": 1}
    assert Post.objects.published().count() == 1
    assert Page.objects.published().count() == 1
    assert Service.objects.published().count() == 1


def test_management_command_publishes_due_content():
    Post.objects.create(title="Cmd post", status=Status.DRAFT, scheduled_at=_past())
    out = StringIO()
    call_command("publish_scheduled", stdout=out)
    assert "Published 1" in out.getvalue()
    assert Post.objects.published().count() == 1


def test_command_is_a_noop_when_nothing_due():
    Post.objects.create(title="Future", status=Status.DRAFT, scheduled_at=_future())
    out = StringIO()
    call_command("publish_scheduled", stdout=out)
    assert "Published 0" in out.getvalue()
    assert Post.objects.published().count() == 0
