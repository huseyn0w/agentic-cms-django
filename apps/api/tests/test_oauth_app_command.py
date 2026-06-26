"""`create_oauth_app` management command + service."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.api import services

pytestmark = pytest.mark.django_db


def test_create_oauth_application_service():
    result = services.create_oauth_application(
        name="Svc client", username=None, redirect_uri="http://localhost/cb/", public=False
    )
    assert result["client_id"]
    assert result["client_secret"]
    from oauth2_provider.models import get_application_model

    assert get_application_model().objects.filter(client_id=result["client_id"]).exists()


def test_create_oauth_application_unknown_user_raises():
    with pytest.raises(LookupError):
        services.create_oauth_application(
            name="x", username="ghost", redirect_uri="http://localhost/cb/", public=False
        )


def test_create_oauth_app_command(make_user):
    make_user("owner")
    out = StringIO()
    call_command("create_oauth_app", "--name", "CLI client", "--user", "owner", stdout=out)
    output = out.getvalue()
    assert "client_id:" in output
    assert "client_secret:" in output


def test_create_oauth_app_command_unknown_user(db):
    with pytest.raises(CommandError):
        call_command("create_oauth_app", "--user", "nobody")
