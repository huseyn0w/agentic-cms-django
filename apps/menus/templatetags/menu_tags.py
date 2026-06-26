"""Template tag exposing a managed menu's resolved links to the public shell."""

from __future__ import annotations

from django import template

from apps.menus import services

register = template.Library()


@register.simple_tag
def menu_items(slug: str) -> list[dict[str, str]]:
    """Return ``[{label, url}]`` for the menu ``slug`` (empty if it doesn't exist).

    Usage: ``{% menu_items "primary" as items %}`` then loop, with a built-in
    fallback when ``items`` is empty.
    """
    return services.get_menu_items(slug)
