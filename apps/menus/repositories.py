"""Menus data-access layer. The single home for menu ORM access."""

from __future__ import annotations

from django.db.models import Prefetch, QuerySet
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
    def top_level(menu: Menu) -> QuerySet:
        """Root items (no parent) in order, with each item's children prefetched.

        The ``children`` prefetch carries the same ``select_related`` so rendering
        a nested menu never issues a per-child query (no N+1).
        """
        children = Prefetch("children", queryset=MenuItem.objects.select_related(*_WITH_TARGET))
        return (
            menu.items.filter(parent__isnull=True)
            .select_related(*_WITH_TARGET)
            .prefetch_related(children)
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
    def top_level_choices(menu: Menu, exclude: MenuItem | None = None) -> QuerySet:
        """Root items eligible to be a parent (one-level nesting; never self)."""
        qs = menu.items.filter(parent__isnull=True)
        if exclude is not None:
            qs = qs.exclude(pk=exclude.pk)
        return qs

    @staticmethod
    def delete(item: MenuItem) -> None:
        item.delete()

    @staticmethod
    def swap_positions(a: MenuItem, b: MenuItem) -> None:
        a.position, b.position = b.position, a.position
        a.save(update_fields=["position"])
        b.save(update_fields=["position"])
