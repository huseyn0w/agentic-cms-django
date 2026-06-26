"""API data-access for auth tokens + OAuth applications (the home for that ORM)."""

from __future__ import annotations

from rest_framework.authtoken.models import Token


class TokenRepository:
    @staticmethod
    def get_or_create_for(user) -> str:
        token, _ = Token.objects.get_or_create(user=user)
        return token.key


class OAuthApplicationRepository:
    """Create django-oauth-toolkit Applications (OAuth clients)."""

    @staticmethod
    def create(*, name: str, user=None, redirect_uri: str, public: bool) -> dict:
        from oauth2_provider.generators import (
            generate_client_id,
            generate_client_secret,
        )
        from oauth2_provider.models import get_application_model

        Application = get_application_model()
        client_id = generate_client_id()
        # Generate the secret up-front so the plaintext can be returned to the
        # operator: DOT may hash client_secret on save (then it is unrecoverable).
        client_secret = generate_client_secret()
        client_type = Application.CLIENT_PUBLIC if public else Application.CLIENT_CONFIDENTIAL
        app = Application.objects.create(
            name=name,
            user=user,
            client_id=client_id,
            client_secret=client_secret,
            client_type=client_type,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            redirect_uris=redirect_uri,
        )
        return {
            "client_id": app.client_id,
            "client_secret": client_secret,
            "client_type": app.client_type,
            "authorization_grant_type": app.authorization_grant_type,
        }
