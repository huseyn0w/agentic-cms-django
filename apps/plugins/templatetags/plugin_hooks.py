from django import template
from django.utils.safestring import mark_safe

from apps.plugins import hooks

register = template.Library()


@register.simple_tag(takes_context=True)
def hook(context, name, **kwargs):
    """Render a template region: emit HTML from plugins registered for `name`."""
    return hooks.render_hook(name, context=context, **kwargs)


@register.simple_tag
def post_content(post):
    """Render a post's body after running it through the `post_content` filters.

    The stored body is already nh3-sanitized; plugin filters are trusted code
    (operator-installed), so the result is rendered as safe HTML.
    """
    return mark_safe(hooks.apply_filters("post_content", post.body, post=post))
