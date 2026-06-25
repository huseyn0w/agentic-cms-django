"""Public menu services — resolve a managed menu into render-ready link dicts.

The view/template tag stays at the boundary; all data access goes through
``MenuRepository``. Returns plain dicts so templates never touch the ORM.
"""

from __future__ import annotations

from .repositories import MenuRepository


def get_menu_items(slug: str) -> list[dict]:
    """Resolved nav tree for the menu ``slug`` in order, or ``[]``.

    Returns one dict per top-level item — ``{label, url, children}`` — where
    ``children`` is the ordered list of nested ``{label, url, children}`` (always
    present, possibly empty, so templates iterate uniformly). Labels and URLs are
    resolved per item (content links localise via the linked object's translated
    title); an empty list lets callers fall back to built-in defaults.
    """
    menu = MenuRepository.get_by_slug(slug)
    if menu is None:
        return []
    return [_node(item) for item in MenuRepository.top_level(menu)]


def _node(item) -> dict:
    """Render-ready dict for one item plus its ordered children (one level deep)."""
    children = sorted(item.children.all(), key=lambda c: (c.position, c.id))
    return {
        "label": item.get_label(),
        "url": item.get_url(),
        "children": [
            {"label": c.get_label(), "url": c.get_url(), "children": []} for c in children
        ],
    }
