"""Public read API viewsets + health probes.

Viewsets are the HTTP boundary: ``get_queryset`` delegates to ``api.services``
(which uses content repositories) and serializers own representation. Read access
is public; the write/MCP surfaces are separate and auth-gated.
"""

from __future__ import annotations

from django.conf import settings
from django.http import JsonResponse
from django.utils import translation
from rest_framework import permissions, viewsets

from . import serializers, services
from .permissions import OAuth2ReadWriteScopeFloor


class LanguageScopedMixin:
    """Activate a requested ``?lang=`` (if configured) for this request only.

    The API lives outside ``i18n_patterns``, so without this parler serialises the
    default language. ``?lang=de`` lets a client pull German translations.
    """

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        lang = request.query_params.get("lang")
        if lang and lang in dict(settings.LANGUAGES):
            translation.activate(lang)


class PostViewSet(LanguageScopedMixin, viewsets.ModelViewSet):
    """Posts: public read, gated write.

    Reads (list/retrieve) are public and scoped to published posts. Writes require
    the matching model permission (DjangoModelPermissions: add/change/delete_post)
    and are owner-scoped for non-managers; publish state is gated server-side in the
    service (``gate_publish_state``), so the API can't be used to bypass it.
    """

    lookup_field = "slug"
    # Model permissions (anon read, perm-gated write) PLUS an OAuth scope floor
    # that only applies to OAuth-authenticated requests (read for safe methods,
    # write otherwise). Token/Session clients are unaffected by the scope floor.
    permission_classes = [
        permissions.DjangoModelPermissionsOrAnonReadOnly,
        OAuth2ReadWriteScopeFloor,
    ]

    def get_queryset(self):
        # Reads (and the permission check's model probe for anon writers) use the
        # published set; authenticated writers get their owner-scoped set.
        if (
            self.request.method in permissions.SAFE_METHODS
            or not self.request.user.is_authenticated
        ):
            return services.published_posts()
        return services.editable_posts(self.request.user)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return serializers.PostWriteSerializer
        if self.action == "retrieve":
            return serializers.PostDetailSerializer
        return serializers.PostSerializer


class PageViewSet(LanguageScopedMixin, viewsets.ReadOnlyModelViewSet):
    lookup_field = "slug"

    def get_queryset(self):
        return services.published_pages()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return serializers.PageDetailSerializer
        return serializers.PageSerializer


class ServiceViewSet(LanguageScopedMixin, viewsets.ReadOnlyModelViewSet):
    lookup_field = "slug"

    def get_queryset(self):
        return services.published_services()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return serializers.ServiceDetailSerializer
        return serializers.ServiceSerializer


class CategoryViewSet(LanguageScopedMixin, viewsets.ReadOnlyModelViewSet):
    lookup_field = "slug"
    serializer_class = serializers.CategorySerializer

    def get_queryset(self):
        return services.all_categories()


class TagViewSet(LanguageScopedMixin, viewsets.ReadOnlyModelViewSet):
    lookup_field = "slug"
    serializer_class = serializers.TagSerializer

    def get_queryset(self):
        return services.all_tags()


# --- Health / readiness (plain JSON, no DRF machinery needed) --- #
def health(request) -> JsonResponse:
    """Liveness: the process is up and serving."""
    return JsonResponse({"status": "ok"})


def readiness(request) -> JsonResponse:
    """Readiness: the app can reach its database."""
    ok = services.database_ok()
    return JsonResponse(
        {"status": "ok" if ok else "unavailable", "database": ok},
        status=200 if ok else 503,
    )
