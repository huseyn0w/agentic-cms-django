import datetime

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone

User = get_user_model()


@pytest.fixture
def make_user(db):
    def _make(username: str, role: str | None = None, **extra):
        user = User.objects.create_user(username=username, password="pw", **extra)
        if role:
            user.groups.add(Group.objects.get(name=role))
        return user

    return _make


@pytest.fixture
def oauth_app(db):
    """A confidential OAuth Application for issuing test access tokens."""
    from oauth2_provider.models import get_application_model

    Application = get_application_model()
    return Application.objects.create(
        name="Test Client",
        client_type=Application.CLIENT_CONFIDENTIAL,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
    )


@pytest.fixture
def oauth_bearer(oauth_app):
    """Mint a Bearer access token for ``user`` with the given scope/expiry.

    Uses django-oauth-toolkit's models directly — a unit test does not need to
    drive the full authorization-code + PKCE browser flow to validate that a
    valid Bearer token authenticates.
    """
    from oauth2_provider.models import get_access_token_model

    AccessToken = get_access_token_model()

    counter = {"n": 0}

    def _headers(user, scope: str = "read", *, expired: bool = False):
        counter["n"] += 1
        expires = timezone.now() + datetime.timedelta(seconds=-3600 if expired else 3600)
        token = AccessToken.objects.create(
            user=user,
            application=oauth_app,
            token=f"tok-{user.pk}-{counter['n']}",
            scope=scope,
            expires=expires,
        )
        return {"HTTP_AUTHORIZATION": f"Bearer {token.token}"}

    return _headers
