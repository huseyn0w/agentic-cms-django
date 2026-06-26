"""Site search over published posts, pages and services.

Orchestration only: this service decides which content types to search, cleans the
query and merges/sorts the results. All ORM access (the Postgres full-text path and
the DB-agnostic fallback) lives in ``apps.search.repositories.ContentSearchRepository``.

Translated fields live on parler translation tables, so matching is scoped to the
*active* language's translation row — a term that only exists in another language
must not surface the record.
"""

from __future__ import annotations

from apps.content.models import Page, Post, Service

from .repositories import ContentSearchRepository

# Translated fields searched per model, highest-signal first.
_POST_FIELDS = ("title", "excerpt", "body")
_PAGE_FIELDS = ("title", "body")
_SERVICE_FIELDS = ("title", "summary", "description")

# Upper bound on the query length we pass to the DB (cheap DoS guard).
_MAX_QUERY_LENGTH = 200


def search_content(query: str, language_code: str) -> list:
    """Search published posts, pages and services, most relevant first.

    Returns a flat list of model instances (mixed Post/Page/Service); a blank query
    yields an empty list. Drafts, unpublished and ``noindex`` items are excluded.
    """
    query = (query or "").strip()[:_MAX_QUERY_LENGTH]
    if not query:
        return []

    results = ContentSearchRepository.match(Post, query, language_code, _POST_FIELDS)
    results += ContentSearchRepository.match(Page, query, language_code, _PAGE_FIELDS)
    results += ContentSearchRepository.match(Service, query, language_code, _SERVICE_FIELDS)
    results.sort(key=lambda obj: obj.search_rank, reverse=True)
    return results
