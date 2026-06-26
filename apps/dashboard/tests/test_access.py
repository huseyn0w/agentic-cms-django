import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_anonymous_redirected_to_login(client):
    response = client.get(reverse("dashboard:home"))
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


def test_user_without_access_admin_forbidden(client, make_user):
    client.force_login(make_user("sub", role="Subscriber"))
    assert client.get(reverse("dashboard:home")).status_code == 403


def test_author_can_reach_dashboard(client, make_user):
    client.force_login(make_user("auth", role="Author"))
    assert client.get(reverse("dashboard:home")).status_code == 200


def test_users_section_requires_manage_users(client, make_user):
    client.force_login(make_user("ed", role="Editor"))  # no manage_users
    assert client.get(reverse("dashboard:user_list")).status_code == 403


def test_settings_section_requires_manage_settings(client, make_user):
    client.force_login(make_user("ed", role="Editor"))  # no manage_settings
    assert client.get(reverse("dashboard:settings")).status_code == 403


def test_dashboard_shell_has_dark_toggle_and_landmarks(client, make_user):
    """Admin shell carries the no-FOUC dark init, a theme toggle and #content (U4)."""
    client.force_login(make_user("ed", role="Editor"))
    html = client.get(reverse("dashboard:home")).content.decode()
    assert "admin-theme" in html  # no-FOUC localStorage key + toggle persistence
    assert "Switch to" in html  # dark/light toggle aria-label
    assert 'id="content"' in html
    assert "bg-surface" in html and "bg-white" not in html  # tokenised, dark-ready
