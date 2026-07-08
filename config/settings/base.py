"""
Base settings shared by every environment.

Environment-specific modules (dev, prod, test) import everything from here with
``from .base import *`` and then override what they need. All secrets and
deployment-specific values come from environment variables via django-environ.
"""

from pathlib import Path

import environ

from config.storages import build_storages

# config/settings/base.py -> config/settings -> config -> <repo root>
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
)

# Load a .env file if present (no-op in environments that inject real env vars).
env_file = BASE_DIR / ".env"
if env_file.exists():
    env.read_env(str(env_file))

# --------------------------------------------------------------------------- #
# Core
# --------------------------------------------------------------------------- #
# SECRET_KEY is intentionally NOT defined here: each environment module owns it,
# so there is no insecure shared default that could leak into a real deployment.
# (dev provides a throwaway fallback; prod requires the env var; test uses a stub.)
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# Tell browsers never to MIME-sniff responses — set in every environment so that
# served uploads (and everything else) carry X-Content-Type-Options: nosniff.
SECURE_CONTENT_TYPE_NOSNIFF = True

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.sitemaps",
    # Third-party
    "django_vite",
    "parler",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.github",
    "django_recaptcha",
    "rest_framework",
    "rest_framework.authtoken",
    # OAuth 2.1 provider (PKCE) — an additional auth floor for the API/MCP.
    "oauth2_provider",
    # Local apps
    "apps.accounts",
    "apps.content",
    "apps.media",
    "apps.dashboard",
    "apps.themes",
    "apps.plugins",
    "apps.seo",
    "apps.comments",
    "apps.search",
    "apps.menus",
    "apps.api",
    "apps.mcp",
    "apps.core",
    # Plugins (live in the top-level plugins/ directory)
    "plugins.reading_time",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # LocaleMiddleware activates the request language from the URL prefix
    # (i18n_patterns) / Accept-Language; must sit after sessions, before common.
    "django.middleware.locale.LocaleMiddleware",
    # Re-applies the operator's cookie-selected UI language on the admin surfaces
    # (/dashboard/, /library/), which live outside i18n_patterns and would
    # otherwise be pinned to the default language by LocaleMiddleware.
    "apps.core.middleware.AdminLocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # allauth: required for account state on every request.
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "config.urls"

# Themes live here; each is a directory with a theme.json and optional templates/.
THEMES_DIR = BASE_DIR / "themes"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        # APP_DIRS must be False to specify loaders explicitly. The theme loader
        # runs first so an active theme can override any project/app template.
        "APP_DIRS": False,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.i18n",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site_settings",
                "apps.core.context_processors.i18n_alternates",
                "apps.seo.context_processors.seo_settings",
            ],
            "loaders": [
                "apps.themes.loaders.ThemeLoader",
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --------------------------------------------------------------------------- #
# Database — Postgres by default; DATABASE_URL wins if provided.
# Kept ORM-level and DB-agnostic so MySQL works on shared hosting.
# --------------------------------------------------------------------------- #
if env.str("DATABASE_URL", default=""):
    DATABASES = {"default": env.db("DATABASE_URL")}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB", default="cmstack_django"),
            "USER": env("POSTGRES_USER", default="cmstack_django"),
            "PASSWORD": env("POSTGRES_PASSWORD", default="cmstack_django"),
            "HOST": env("POSTGRES_HOST", default="db"),
            "PORT": env("POSTGRES_PORT", default="5432"),
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------- #
# Authentication — custom user + django-allauth (local + social login)
# --------------------------------------------------------------------------- #
AUTH_USER_MODEL = "accounts.User"

SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# allauth (65.3.x settings API). Login by username OR email, like the reference CMS.
ACCOUNT_AUTHENTICATION_METHOD = "username_email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = "optional"
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_LOGOUT_ON_GET = False

# Throttle brute-force attempts against auth endpoints. Each limit keeps both an
# IP bucket and a per-account ("key") bucket so an attacker can't bypass the
# block by spreading a single-account attack across many IPs.
# NOTE: rate limits use Django's cache, which defaults to per-process LocMemCache.
# A shared backend (Redis) is needed for accurate limits under multiple workers;
# that arrives with the production/infra work in a later phase.
ACCOUNT_RATE_LIMITS = {
    "login_failed": "5/5m/ip,5/5m/key",
    "signup": "20/h/ip",
    "reset_password": "5/h/ip",
}

# Social sign-in (Google + GitHub). Credentials come from the environment (never
# committed); each provider stays registered even when unset so the rest of auth
# still works. A provider only *activates* when its env keys are present — with no
# keys its ``APPS`` list is empty, so allauth has no configured OAuth app to log in
# with and the button stays inert (dev/CI run without any social keys).
GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID", default="")
GOOGLE_CLIENT_SECRET = env("GOOGLE_CLIENT_SECRET", default="")
GITHUB_CLIENT_ID = env("GITHUB_CLIENT_ID", default="")
GITHUB_CLIENT_SECRET = env("GITHUB_CLIENT_SECRET", default="")


def _social_app(client_id: str, secret: str) -> list[dict]:
    """One configured OAuth app, or an empty list when the env keys are absent."""
    if client_id and secret:
        return [{"client_id": client_id, "secret": secret, "key": ""}]
    return []


SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APPS": _social_app(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    },
    "github": {
        "APPS": _social_app(GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET),
        "SCOPE": ["read:user", "user:email"],
    },
}

# New self-service signups are placed in a default role (see apps.accounts.roles).
SOCIALACCOUNT_LOGIN_ON_GET = False

# reCAPTCHA v3 spam protection. Keys come from the environment; when either is
# blank the captcha field is simply not added to public forms (see
# apps.comments.forms.recaptcha_enabled), so the site runs fine without keys in
# dev/CI. Empty (not the library's built-in test keys) so the security check stays
# quiet without hiding a real misconfiguration.
RECAPTCHA_PUBLIC_KEY = env("RECAPTCHA_PUBLIC_KEY", default="")
RECAPTCHA_PRIVATE_KEY = env("RECAPTCHA_PRIVATE_KEY", default="")

# Recipient for public contact-form submissions. Empty → the contact observer is a
# no-op (the form still validates and thanks the visitor), so dev/CI need no inbox.
CONTACT_EMAIL = env("CONTACT_EMAIL", default="")

# --------------------------------------------------------------------------- #
# Password validation
# --------------------------------------------------------------------------- #
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------------------------------- #
# Internationalization
# --------------------------------------------------------------------------- #
# Default language. Kept as a bare code ("en", not "en-us") so it matches the
# LANGUAGES keys below and parler's per-language translation lookups.
LANGUAGE_CODE = env("DJANGO_LANGUAGE_CODE", default="en")

# The languages the public site is offered in. Content (posts/pages/taxonomy) is
# translated per-language via django-parler; the URL carries a language prefix
# for every non-default language (see i18n_patterns in config/urls.py), which is
# what makes the hreflang alternates point at distinct, crawlable URLs.
LANGUAGES = [
    ("en", "English"),
    ("de", "Deutsch"),
    ("ru", "Russian"),
]

LOCALE_PATHS = [BASE_DIR / "locale"]

TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Opt into Django 6.0's behaviour now: bare-domain URLField input defaults to https.
FORMS_URLFIELD_ASSUME_HTTPS = True

# django-parler: one translation row per language, falling back to the default
# language when a translation is missing so a half-translated site still renders.
PARLER_DEFAULT_LANGUAGE_CODE = LANGUAGE_CODE
# Keyed by SITE_ID (not None) so parler's language-tab helper, which looks up
# PARLER_LANGUAGES[SITE_ID] directly, finds the configured languages.
PARLER_LANGUAGES = {
    SITE_ID: tuple({"code": code} for code, _name in LANGUAGES),
    "default": {
        "fallback": LANGUAGE_CODE,
        "hide_untranslated": False,
    },
}

# --------------------------------------------------------------------------- #
# Static & media files
# --------------------------------------------------------------------------- #
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Vite build output is collected as static so whitenoise can serve it.
STATICFILES_DIRS = [BASE_DIR / "frontend" / "dist"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Swappable media storage (local disk by default; S3-compatible when USE_S3_MEDIA
# is set). The selection logic lives in config.storages so it stays unit-testable.
STORAGES = build_storages(env)

# --------------------------------------------------------------------------- #
# Django REST Framework (public read API + gated write API)
# --------------------------------------------------------------------------- #
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    # Token for programmatic clients; session so the dashboard can reuse the API;
    # OAuth2 (django-oauth-toolkit) as the OAuth 2.1 auth floor for API + MCP.
    # OAuth is AUTHENTICATION ONLY — the per-view permission classes and the MCP
    # per-tool re-verification still own authorization.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
        "oauth2_provider.contrib.rest_framework.OAuth2Authentication",
    ],
    # Read access is public; write endpoints require the matching model permission.
    # (Keep the default AnonymousUser so DjangoModelPermissions allows anon reads.)
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
}

# --------------------------------------------------------------------------- #
# OAuth 2.1 provider (django-oauth-toolkit)
# --------------------------------------------------------------------------- #
# An OAuth 2.1 authorization server for the API/MCP. PKCE is required (no
# implicit grant, no client secrets needed for public clients); access is scoped
# to "read"/"write" with "read" the default. Tokens are presented as
# ``Authorization: Bearer <token>`` and validated by OAuth2Authentication (added
# to the DRF auth classes above). It works with the custom user model out of the
# box because OAuth links the token to AUTH_USER_MODEL via a FK.
OAUTH2_PROVIDER = {
    "PKCE_REQUIRED": True,
    "SCOPES": {
        "read": "Read access to the API and MCP tools",
        "write": "Write access to the API and MCP tools",
    },
    "DEFAULT_SCOPES": ["read"],
}

# --------------------------------------------------------------------------- #
# django-vite — bridges the Vite build (Tailwind + Alpine) into Django templates.
# In dev_mode the template tags point at the Vite dev server (HMR); otherwise
# they read the build manifest produced by `npm run build`.
# --------------------------------------------------------------------------- #
DJANGO_VITE = {
    "default": {
        "dev_mode": env.bool("DJANGO_VITE_DEV_MODE", default=False),
        "dev_server_port": env.int("DJANGO_VITE_DEV_SERVER_PORT", default=5173),
        "manifest_path": BASE_DIR / "frontend" / "dist" / ".vite" / "manifest.json",
    }
}
