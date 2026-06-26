"""OAuth-scope permission that only bites OAuth-authenticated requests.

Token / Session authenticated requests have no OAuth scopes, so the existing
model-permission gates remain the sole authorization check for them. When a
request is authenticated with an OAuth2 Bearer token, we additionally require
the read/write scope appropriate to the HTTP method — keeping OAuth honest
without changing how Token/Session clients behave.
"""

from __future__ import annotations

from oauth2_provider.contrib.rest_framework import (
    OAuth2Authentication,
    TokenHasReadWriteScope,
)
from rest_framework.permissions import BasePermission


class OAuth2ReadWriteScopeFloor(BasePermission):
    """Require the read/write scope for OAuth tokens; pass everything else through.

    This is an additive floor: it never grants access on its own (callers combine
    it with the model-permission classes). It only DENIES an OAuth request whose
    token lacks the scope matching the method (read for safe, write otherwise).
    """

    def has_permission(self, request, view) -> bool:
        authenticator = getattr(request, "successful_authenticator", None)
        if not isinstance(authenticator, OAuth2Authentication):
            return True
        return TokenHasReadWriteScope().has_permission(request, view)
