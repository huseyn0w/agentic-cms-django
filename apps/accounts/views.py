from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, UpdateView

from . import services
from .forms import ProfileForm


class AuthorDetailView(ListView):
    """Public author archive: bio + their published posts + ProfilePage JSON-LD."""

    template_name = "accounts/author_detail.html"
    context_object_name = "posts"
    paginate_by = 10

    def get_queryset(self):
        self.author = services.get_author_for_view(self.kwargs["pk"])
        return services.author_posts(self.author)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["author"] = self.author
        return ctx


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    """Self-service profile editor at ``/account/`` for the logged-in user."""

    form_class = ProfileForm
    template_name = "accounts/profile_form.html"
    success_url = reverse_lazy("accounts:profile")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Profile updated.")
        return super().form_valid(form)
