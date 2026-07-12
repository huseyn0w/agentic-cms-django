"""Test settings that run the suite against PostgreSQL.

Identical to the SQLite ``test`` settings in every respect except the database
backend. The SQLite suite only exercises the ``icontains`` fallback in
``apps/search/repositories.py``; running the same tests on PostgreSQL (in CI)
exercises the ``SearchVector``/``SearchQuery``/``SearchRank`` full-text-search
branch that is unreachable on SQLite. Select it with
``pytest --ds=config.settings.test_postgres``.
"""

import os

from .test import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "agentic_cms_django"),
        "USER": os.environ.get("POSTGRES_USER", "agentic_cms_django"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "agentic_cms_django"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}
