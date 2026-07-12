"""Root URL configuration for AgenticCms-Django."""

from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from apps.api import views as api_views
from apps.content.feeds import LatestPostsFeed
from apps.seo import views as seo_views
from apps.seo.sitemaps import sitemaps

# Non-public, non-translated surfaces: the admin/dashboard UI, auth, media files
# and the language-switch endpoint. These keep stable, prefix-free URLs.
urlpatterns = [
    # The custom panel at /dashboard/ is the primary admin. The Django admin is
    # kept as a superuser-only fallback: it requires is_staff, which NO AgenticCms-Django
    # role grants, so dashboard users (Editors/Authors/etc.) cannot reach it.
    path("admin/", admin.site.urls),
    # django-allauth: login, signup, logout, password reset, social login.
    path("accounts/", include("allauth.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("i18n/", include("django.conf.urls.i18n")),
    # Public REST API (language-agnostic, outside i18n_patterns).
    path("api/", include("apps.api.urls")),
    # MCP server (token-authenticated tool surface for AI clients).
    path("api/mcp/", include("apps.mcp.urls")),
    # OAuth 2.1 provider (authorize/token/revoke endpoints), outside i18n.
    path("oauth/", include("oauth2_provider.urls", namespace="oauth2_provider")),
    # Liveness + readiness probes.
    path("health/", api_views.health, name="health"),
    path("health/ready/", api_views.readiness, name="health_ready"),
    # Machine-readable surfaces, served at the root, unprefixed by language.
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path("rss.xml", LatestPostsFeed(), name="rss"),
    path("robots.txt", seo_views.robots_txt, name="robots_txt"),
    path("llms.txt", seo_views.llms_txt, name="llms_txt"),
    path("llms-full.txt", seo_views.llms_full_txt, name="llms_full_txt"),
    path("", include("apps.media.urls")),
]

# Public content is offered per language. prefix_default_language=False keeps the
# default language on clean, prefix-free URLs (/blog/<slug>/) while every other
# language is served under its code (/de/blog/<slug>/) — distinct URLs that the
# hreflang alternates point at. LocaleMiddleware activates the language from the
# prefix on each request.
urlpatterns += i18n_patterns(
    path("", include("apps.content.urls")),
    path("", include("apps.search.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.core.urls")),
    prefix_default_language=False,
)

# Serve user-uploaded media in development. In production these are served by the
# web server / object storage in front of the app.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
