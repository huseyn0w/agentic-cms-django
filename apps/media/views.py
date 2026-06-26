from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView

from . import services
from .forms import MediaUploadForm
from .models import MediaAsset


class MediaLibraryView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "media.view_mediaasset"
    template_name = "media/library.html"
    context_object_name = "assets"
    paginate_by = 24

    def get_queryset(self):
        return services.list_assets()


class MediaUploadView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "media.add_mediaasset"
    template_name = "media/upload.html"
    form_class = MediaUploadForm
    success_url = reverse_lazy("media:library")

    def form_valid(self, form):
        services.prepare_upload(form.instance, self.request.user)
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(services.upload_constraints())
        return ctx


# django-stubs flags DeleteView's DeletionMixin/BaseDetailView `object` MRO clash (false positive).
class MediaDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):  # type: ignore[misc]
    permission_required = "media.delete_mediaasset"
    model = MediaAsset
    success_url = reverse_lazy("media:library")
    # Delete only on POST; no confirmation GET page needed for this minimal UI.
    http_method_names = ["post"]

    def get_queryset(self):
        return services.list_assets()
