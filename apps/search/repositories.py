"""Search data-access layer (repository).

Owns every ORM detail of site search: the published/noindex base queryset, the
PostgreSQL full-text path and the DB-agnostic ``icontains`` fallback. The search
service orchestrates which models to search and how to merge/sort results, but all
querying lives here.
"""

from __future__ import annotations

from django.db import connection
from django.db.models import Q


def _is_postgres() -> bool:
    return connection.vendor == "postgresql"


def _annotate_display(obj, label: str) -> None:
    """Attach uniform display attributes the results template relies on.

    ``search_excerpt`` is normalised here because Pages have no ``excerpt`` field
    and Services lead with a ``summary``; reading a missing attribute in the
    template would silently swallow an AttributeError.
    """
    obj.search_type = label
    obj.search_excerpt = getattr(obj, "excerpt", "") or getattr(obj, "summary", "") or ""


class ContentSearchRepository:
    @staticmethod
    def match(model, query: str, language_code: str, fields: tuple[str, ...]) -> list:
        """Return published ``model`` instances matching ``query`` in ``language_code``.

        Each instance carries ``search_rank`` (relevance on Postgres, ``0.0`` on the
        fallback), ``search_type`` and ``search_excerpt``. ``noindex`` items are
        withheld so on-site search matches the sitemap/crawler surface.
        """
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
