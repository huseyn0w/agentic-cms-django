from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.views import View
from django.views.generic import DetailView, ListView

from apps.comments import services as comment_services

from . import services


class PostListView(ListView):
    template_name = "content/post_list.html"
    context_object_name = "posts"
    paginate_by = 10

    def get_queryset(self):
        return services.list_published_posts()


class CategoryPostListView(ListView):
    template_name = "content/post_list.html"
    context_object_name = "posts"
    paginate_by = 10

    def get_queryset(self):
        self.category = services.get_category(self.kwargs["slug"])
        return services.posts_in_category(self.category)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["taxonomy"] = self.category
        # Distinct key (the shared template also renders tag archives via
        # ``taxonomy``) so the per-category RSS autodiscovery link is emitted
        # only on category pages.
        ctx["category"] = self.category
        return ctx


class TagPostListView(ListView):
    template_name = "content/post_list.html"
    context_object_name = "posts"
    paginate_by = 10

    def get_queryset(self):
        self.tag = services.get_tag(self.kwargs["slug"])
        return services.posts_with_tag(self.tag)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["taxonomy"] = self.tag
        return ctx


class PostDetailView(DetailView):
    template_name = "content/post_detail.html"
    context_object_name = "post"

    def get_object(self, queryset=None):
        return services.get_post_for_view(self.kwargs["slug"], self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            services.post_detail_context(self.object, self.request.user, ctx.get("comment_form"))
        )
        return ctx

    def post(self, request, *args, **kwargs):
        """Submit a comment posted to the post's own URL; map the outcome to HTTP."""
        self.object = self.get_object()
        outcome, form = comment_services.submit_comment(
            self.object, request.user, request.POST, request
        )
        if outcome == comment_services.DISABLED:
            raise Http404
        if outcome == comment_services.LOGIN_REQUIRED:
            return redirect_to_login(self.object.get_absolute_url())
        if outcome == comment_services.RATE_LIMITED:
            return HttpResponse(
                "Too many comments submitted. Please try again in a minute.",
                status=429,
                content_type="text/plain",
            )
        if outcome == comment_services.CREATED:
            messages.success(
                request, "Thanks! Your comment was submitted and is awaiting moderation."
            )
            return redirect(self.object.get_absolute_url() + "#comments")
        return self.render_to_response(self.get_context_data(comment_form=form))


class PostLikeView(View):
    """Toggle the current user's like on a post (POST only).

    Guests are sent to login; authenticated users toggle and return to the post.
    """

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        post = services.get_post_for_action(self.kwargs["slug"])
        if not request.user.is_authenticated:
            return redirect_to_login(post.get_absolute_url())
        services.toggle_post_like(post, request.user)
        return redirect(post.get_absolute_url() + "#likes")


class PageDetailView(DetailView):
    template_name = "content/page_detail.html"
    context_object_name = "page"

    def get_object(self, queryset=None):
        return services.get_page_for_view(self.kwargs["slug"], self.request.user)


class ServiceListView(ListView):
    template_name = "content/service_list.html"
    context_object_name = "services"

    def get_queryset(self):
        return services.list_published_services()


class ServiceDetailView(DetailView):
    template_name = "content/service_detail.html"
    context_object_name = "service"

    def get_object(self, queryset=None):
        return services.get_service_for_view(self.kwargs["slug"], self.request.user)
