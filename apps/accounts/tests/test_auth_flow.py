import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()
pytestmark = pytest.mark.django_db


def test_login_page_renders(client):
    response = client.get(reverse("account_login"))
    assert response.status_code == 200
    assert b"Cmstack-Django" in response.content  # our styled auth layout is in use


def test_signup_page_renders(client):
    response = client.get(reverse("account_signup"))
    assert response.status_code == 200


def test_google_provider_configured():
    assert "google" in settings.SOCIALACCOUNT_PROVIDERS
    # The provider's login entrypoint is wired into the URLconf.
    assert reverse("google_login")


def test_github_provider_installed_and_wired():
    # GitHub is a first-class social provider (§5): its allauth app is installed
    # and its SOCIALACCOUNT_PROVIDERS entry + login URL exist, mirroring Google.
    assert "allauth.socialaccount.providers.github" in settings.INSTALLED_APPS
    assert "github" in settings.SOCIALACCOUNT_PROVIDERS
    assert reverse("github_login")


def test_github_provider_gated_on_env_keys():
    # Like Google, GitHub credentials come from the environment and are never
    # committed. With no env keys set (dev/CI/tests), the provider is registered
    # but carries no configured OAuth app, so it stays inactive/frictionless.
    github = settings.SOCIALACCOUNT_PROVIDERS["github"]
    assert github.get("APPS", []) == []


def test_logout_requires_post(client):
    # GET must not log out (ACCOUNT_LOGOUT_ON_GET is False): an authenticated user
    # gets a confirmation page, and only POST actually ends the session.
    assert settings.ACCOUNT_LOGOUT_ON_GET is False
    user = User.objects.create_user(username="loguser", password="pw")
    client.force_login(user)

    confirm = client.get(reverse("account_logout"))
    assert confirm.status_code == 200

    done = client.post(reverse("account_logout"))
    assert done.status_code == 302
    assert "_auth_user_id" not in client.session


def test_login_by_email_works(client):
    # Reference-CMS parity: users can sign in with email OR username.
    User.objects.create_user(username="dora", email="dora@example.com", password="pw")
    response = client.post(
        reverse("account_login"), {"login": "dora@example.com", "password": "pw"}
    )
    assert response.status_code == 302  # redirected on success
    assert "_auth_user_id" in client.session


def test_login_by_username_works(client):
    User.objects.create_user(username="dora", email="dora@example.com", password="pw")
    response = client.post(reverse("account_login"), {"login": "dora", "password": "pw"})
    assert response.status_code == 302
    assert "_auth_user_id" in client.session


def test_email_required_at_signup():
    assert settings.ACCOUNT_EMAIL_REQUIRED is True
    assert settings.ACCOUNT_AUTHENTICATION_METHOD == "username_email"


def test_rate_limits_configured():
    assert "login_failed" in settings.ACCOUNT_RATE_LIMITS
    # The per-account ("key") bucket must be present, not just per-IP.
    assert "key" in settings.ACCOUNT_RATE_LIMITS["login_failed"]


def test_rate_limit_429_template_exists():
    # allauth renders "429.html" when a limit is hit; a missing template would 500.
    from django.template.loader import get_template

    assert get_template("429.html")


def test_home_shows_auth_links_when_anonymous(client):
    response = client.get(reverse("core:home"))
    assert reverse("account_login").encode() in response.content
    assert reverse("account_signup").encode() in response.content
