"""Per-IP rate limiting on comment submission (§3).

Canon: 8 submissions per minute per client IP (copied from cmstack-ts). The 9th
request in the same minute is rejected with HTTP 429 and creates no comment.
"""

import pytest
from django.contrib.auth import get_user_model

from apps.comments import services as comment_services
from apps.comments.models import Comment
from apps.content.models import Post, Status

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def author():
    return User.objects.create_user(username="writer")


@pytest.fixture
def post(author):
    return Post.objects.create(
        title="Hello", body="<p>x</p>", author=author, status=Status.PUBLISHED
    )


def _submit(client, post, ip="203.0.113.7", body="Great post"):
    return client.post(
        post.get_absolute_url(),
        {"name": "Bob", "email": "b@x.com", "body": body},
        REMOTE_ADDR=ip,
    )


def test_ninth_submission_in_a_minute_is_rejected(client, post):
    # The first COMMENT_RATE_LIMIT submissions succeed…
    for _ in range(comment_services.COMMENT_RATE_LIMIT):
        resp = _submit(client, post)
        assert resp.status_code == 302

    # …the next one from the same IP is throttled (429), and no extra comment saved.
    resp = _submit(client, post)
    assert resp.status_code == 429
    assert Comment.objects.count() == comment_services.COMMENT_RATE_LIMIT


def test_rate_limit_default_is_eight_per_minute():
    # Canon value copied from cmstack-ts (8/min).
    assert comment_services.COMMENT_RATE_LIMIT == 8


def test_a_different_ip_has_its_own_bucket(client, post):
    for _ in range(comment_services.COMMENT_RATE_LIMIT):
        assert _submit(client, post, ip="203.0.113.7").status_code == 302
    # First IP is now blocked…
    assert _submit(client, post, ip="203.0.113.7").status_code == 429
    # …but a fresh IP still gets through (per-IP bucket, not global).
    assert _submit(client, post, ip="198.51.100.42").status_code == 302


def test_x_forwarded_for_is_used_as_the_client_ip(client, post):
    # Behind a proxy the real client IP is the first X-Forwarded-For hop; two
    # requests carrying the same forwarded IP share a bucket even if REMOTE_ADDR
    # differs.
    for i in range(comment_services.COMMENT_RATE_LIMIT):
        resp = client.post(
            post.get_absolute_url(),
            {"name": "Bob", "email": "b@x.com", "body": f"c{i}"},
            REMOTE_ADDR="10.0.0.1",
            HTTP_X_FORWARDED_FOR="203.0.113.99, 10.0.0.1",
        )
        assert resp.status_code == 302
    resp = client.post(
        post.get_absolute_url(),
        {"name": "Bob", "email": "b@x.com", "body": "blocked"},
        REMOTE_ADDR="10.0.0.2",
        HTTP_X_FORWARDED_FOR="203.0.113.99, 10.0.0.2",
    )
    assert resp.status_code == 429
