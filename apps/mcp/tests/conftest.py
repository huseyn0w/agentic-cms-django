import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.authtoken.models import Token

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
def auth_headers():
    def _headers(user):
        return {"HTTP_AUTHORIZATION": f"Token {Token.objects.create(user=user).key}"}

    return _headers
