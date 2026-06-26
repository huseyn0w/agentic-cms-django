"""Menus data-access layer. The single home for menu ORM access."""

from __future__ import annotations

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

from .models import Menu, MenuItem

# Reused link-target join — every item render needs its linked object.
_WITH_TARGET = ("post", "page", "category")


class MenuRepository:
    @staticmethod
    def all() -> QuerySet:
        return Menu.objects.all()

    @staticmethod
    def get(pk: int) -> Menu:
        return get_object_or_404(Menu, pk=pk)

    @staticmethod
    def get_by_slug(slug: str) -> Menu | None:
        return Menu.objects.filter(slug=slug).first()

    @staticmethod
    def items_for(menu: Menu) -> QuerySet:
        """A menu's items in order, with link targets joined to avoid N+1."""
        return menu.items.select_related(*_WITH_TARGET)

    @staticmethod
    def flat_for_tree(menu: Menu) -> list[MenuItem]:
        """ALL of a menu's items in one ordered fetch, ready for a Python tree build.

        A single query (plus one translation prefetch) joins every link target and
        carries the per-item ``position`` ordering, so the service can assemble an
        arbitrary-depth tree in pure Python with NO per-node query at any depth.
        """
        return list(
            menu.items.select_related(*_WITH_TARGET)
            .prefetch_related("translations")
            .order_by("position", "id")
        )

    @staticmethod
    def delete(menu: Menu) -> None:
        menu.delete()


class MenuItemRepository:
    @staticmethod
    def get(menu: Menu, pk: int) -> MenuItem:
        return get_object_or_404(menu.items, pk=pk)

    @staticmethod
    def ordered(menu: Menu) -> list[MenuItem]:
        """All of a menu's items (used by the tree builder in the dashboard)."""
        return list(menu.items.select_related(*_WITH_TARGET))

    @staticmethod
    def siblings(menu: Menu, parent: MenuItem | None) -> list[MenuItem]:
        """An item's ordered sibling group (same menu + same parent)."""
        return list(menu.items.filter(parent=parent))

    @staticmethod
    def next_position(menu: Menu, parent: MenuItem | None = None) -> int:
        """Next position within a sibling group (top level when ``parent`` is None)."""
        last = menu.items.filter(parent=parent).order_by("-position").first()
        return (last.position + 1) if last else 0

    @staticmethod
    def descendant_ids(menu: Menu, item: MenuItem) -> set[int]:
        """Ids of every item beneath ``item`` (any depth), from ONE flat fetch.

        Builds a parent→children adjacency from a single ``(id, parent_id)`` pass
        over the menu's items, then walks it iteratively — no per-node query — so
        cycle prevention scales to arbitrary depth.
        """
        pairs = list(menu.items.values_list("id", "parent_id"))
        children: dict[int, list[int]] = {}
        for child_id, parent_id in pairs:
            if parent_id is not None:
                children.setdefault(parent_id, []).append(child_id)
        result: set[int] = set()
        stack = list(children.get(item.pk, []))
        while stack:
            node = stack.pop()
            if node in result:
                continue
            result.add(node)
            stack.extend(children.get(node, []))
        return result

    @staticmethod
    def eligible_parents(menu: Menu, exclude: MenuItem | None = None) -> QuerySet:
        """Items in this menu that may be chosen as a parent for ``exclude``.

        Any item in the menu EXCEPT the item itself and any of its descendants
        (selecting one of those would create a cycle). When ``exclude`` is a new,
        unsaved item it has no descendants, so every item is eligible.
        """
        qs = menu.items.all()
        if exclude is not None and exclude.pk:
            forbidden = MenuItemRepository.descendant_ids(menu, exclude) | {exclude.pk}
            qs = qs.exclude(pk__in=forbidden)
        return qs

    @staticmethod
    def delete(item: MenuItem) -> None:
        item.delete()

    @staticmethod
    def swap_positions(a: MenuItem, b: MenuItem) -> None:
        a.position, b.position = b.position, a.position
        a.save(update_fields=["position"])
        b.save(update_fields=["position"])

    @staticmethod
    def reorder(menu: Menu, ordered_ids: list[int]) -> None:
        """Assign positions 0..n to this menu's items in the given id order.

        Ids that don't belong to the menu are ignored (scoping guard). Items are
        renumbered within whatever sibling group the caller's order describes;
        each persisted row writes only its ``position``.
        """
        items = {i.pk: i for i in menu.items.all()}
        position = 0
        for pk in ordered_ids:
            item = items.get(pk)
            if item is None:
                continue
            if item.position != position:
                item.position = position
                item.save(update_fields=["position"])
            position += 1
