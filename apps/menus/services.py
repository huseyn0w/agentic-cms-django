"""Public menu services — resolve a managed menu into render-ready link dicts.

The view/template tag stays at the boundary; all data access goes through
``MenuRepository``. Returns plain dicts so templates never touch the ORM.
"""

from __future__ import annotations

from .repositories import MenuRepository


def get_menu_items(slug: str) -> list[dict]:
    """Resolved nav tree for the menu ``slug`` in order, or ``[]``.

    Returns one dict per top-level item — ``{label, url, children}`` — where
    ``children`` is the ordered list of nested ``{label, url, children}`` nodes,
    recursively to ANY depth (always present, possibly empty, so templates iterate
    uniformly). Labels and URLs are resolved per item (content links localise via
    the linked object's translated title); an empty list lets callers fall back to
    built-in defaults.

    The whole tree is assembled in PYTHON from one flat, ordered fetch of the
    menu's items, so there is no N+1 at any depth.
    """
    menu = MenuRepository.get_by_slug(slug)
    if menu is None:
        return []
    return _build_tree(MenuRepository.flat_for_tree(menu))


def _build_tree(items: list) -> list[dict]:
    """Assemble an ordered ``{label,url,children}`` tree from a flat, ordered list.

    ``items`` is already ordered by ``(position, id)`` within the whole menu, so
    grouping by ``parent_id`` preserves each sibling group's order. One pass builds
    a parent→children map of render-ready dicts; a second links them — no ORM.
    """
    children_by_parent: dict[int | None, list[tuple[int, dict]]] = {}
    for item in items:
        node: dict = {"label": item.get_label(), "url": item.get_url(), "children": []}
        children_by_parent.setdefault(item.parent_id, []).append((item.pk, node))

    def attach(parent_id: int | None) -> list[dict]:
        nodes = []
        for pk, node in children_by_parent.get(parent_id, []):
            node["children"] = attach(pk)
            nodes.append(node)
        return nodes

    return attach(None)
