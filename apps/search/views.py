from __future__ import annotations

from django.utils.translation import get_language
from django.views.generic import ListView

from .services import search_content


class SearchView(ListView):
    """Public search results for posts and pages, paginated."""

    template_name = "search/results.html"
    context_object_name = "results"
    paginate_by = 10

    # ListView paginates any sequence; search returns a flat list of mixed
    # Post/Page instances, not a QuerySet — hence the LSP-narrowing override.
    def get_queryset(self) -> list:  # type: ignore[override]
        self.query = self.request.GET.get("q", "").strip()
        if not self.query:
            return []
        return search_content(self.query, get_language())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["query"] = self.query
        return ctx
