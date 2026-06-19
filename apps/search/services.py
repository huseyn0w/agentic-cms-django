"""Site search over published posts and pages.

On PostgreSQL this uses native full-text search (``SearchVector``/``SearchQuery``/
``SearchRank``) for relevance ranking; on every other backend it falls back to a
DB-agnostic ``icontains`` match so the feature works on shared MySQL/SQLite hosts.
The backend is chosen at query time from ``connection.vendor``.

Translated fields live on parler translation tables, so matching is scoped to the
*active* language's translation row (``translations__language_code=<code>``) — a
term that only exists in another language must not surface the record.
"""

from __future__ import annotations

from django.db import connection
from django.db.models import Q

from apps.content.models import Page, Post

# Translated fields searched per model, highest-signal first.
_POST_FIELDS = ("title", "excerpt", "body")
_PAGE_FIELDS = ("title", "body")

# Upper bound on the query length we pass to the DB (cheap DoS guard).
_MAX_QUERY_LENGTH = 200


def _is_postgres() -> bool:
    return connection.vendor == "postgresql"


def _annotate_display(obj, label: str) -> None:
    """Attach uniform display attributes the results template relies on.

    ``search_excerpt`` is normalised here because Pages have no ``excerpt`` field;
    reading it blindly in the template would silently swallow an AttributeError.
    """
    obj.search_type = label
    obj.search_excerpt = getattr(obj, "excerpt", "") or ""


def _search_model(model, query: str, language_code: str, fields: tuple[str, ...]) -> list:
    """Return published ``model`` instances matching ``query`` in ``language_code``.

    Each returned instance carries a ``search_rank`` float (relevance on Postgres,
    ``0.0`` on the fallback) and a ``search_type`` label for the template.
    """
    # `noindex` items are withheld from discovery surfaces (sitemap, crawlers); keep
    # the on-site search consistent so a "hide from search engines" item stays hidden.
    base = (
        model.objects.published()
        .filter(noindex=False)
        .language(language_code)
        .select_related("author")
    )
    label = model._meta.verbose_name.title()

    if _is_postgres():
        from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector

        vector = SearchVector(*(f"translations__{f}" for f in fields))
        search_query = SearchQuery(query)
        qs = (
            base.filter(translations__language_code=language_code)
            .annotate(rank=SearchRank(vector, search_query))
            .filter(rank__gt=0)
            .order_by("-rank")
        )
        results = list(qs)
        for obj in results:
            obj.search_rank = float(obj.rank)
            _annotate_display(obj, label)
        return results

    # DB-agnostic fallback: substring match on the active language's translation.
    text = Q()
    for field in fields:
        text |= Q(**{f"translations__{field}__icontains": query})
    qs = base.filter(Q(translations__language_code=language_code) & text).distinct()
    results = list(qs)
    for obj in results:
        obj.search_rank = 0.0
        _annotate_display(obj, label)
    return results


def search_content(query: str, language_code: str) -> list:
    """Search published posts and pages, most relevant first.

    Returns a flat list of model instances (mixed Post/Page); a blank query
    yields an empty list. Drafts and unpublished items are always excluded.
    """
    query = (query or "").strip()[:_MAX_QUERY_LENGTH]
    if not query:
        return []

    results = _search_model(Post, query, language_code, _POST_FIELDS)
    results += _search_model(Page, query, language_code, _PAGE_FIELDS)
    results.sort(key=lambda obj: obj.search_rank, reverse=True)
    return results
