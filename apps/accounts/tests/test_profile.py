"""Self-service profile editor at /account/ (F10)."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def member():
    return User.objects.create_user(username="member", password="pw", email="m@example.com")


def test_profile_requires_login(client):
    response = client.get(reverse("accounts:profile"))
    assert response.status_code == 302
    assert reverse("account_login") in response.url


def test_member_can_view_profile(client, member):
    client.force_login(member)
    assert client.get(reverse("accounts:profile")).status_code == 200


def test_member_can_update_profile(client, member):
    client.force_login(member)
    response = client.post(
        reverse("accounts:profile"),
        {
            "first_name": "Mem",
            "last_name": "Ber",
            "bio": "Hello there.",
            "website": "https://me.example",
        },
    )
    assert response.status_code == 302
    member.refresh_from_db()
    assert member.first_name == "Mem"
    assert member.bio == "Hello there."
    assert member.website == "https://me.example"
