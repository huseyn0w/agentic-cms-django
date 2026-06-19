from django.views.generic import TemplateView

from apps.content.models import Post, Service


class HomeView(TemplateView):
    """Public landing page. Showcases the CMS with its own real published
    content (recent posts and services) rather than mock previews."""

    template_name = "core/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["recent_posts"] = (
            Post.objects.published().select_related("author").prefetch_related("categories")[:3]
        )
        ctx["featured_services"] = Service.objects.published()[:3]
        return ctx
