from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import TemplateView

from . import services
from .forms import ContactForm


class HomeView(TemplateView):
    """Public landing page. Showcases the CMS with its own real published
    content (recent posts and services) rather than mock previews."""

    template_name = "core/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(services.home_context())
        return ctx


class ContactView(View):
    """Public contact form. Thin HTTP boundary: parse → service → respond."""

    template_name = "core/contact.html"

    def get(self, request):
        return render(request, self.template_name, {"form": ContactForm()})

    def post(self, request):
        sent, form = services.submit_contact(request.POST)
        if sent:
            messages.success(request, "Thanks! Your message has been sent.")
            return redirect("core:contact")
        return render(request, self.template_name, {"form": form})
