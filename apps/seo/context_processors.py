from .models import SeoSettings


def seo_settings(request):
    """Expose the SEO settings singleton to every template as `seo`."""
    return {"seo": SeoSettings.load()}
