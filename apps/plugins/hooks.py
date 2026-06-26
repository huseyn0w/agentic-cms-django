"""
A small extensibility hook registry: **actions**, **filters**, and **region
hooks**, the extension mechanism plugins use to change behavior without editing
core. This complements Django's own signals (used for model lifecycle events).

- ``add_action`` / ``do_action`` — fire-and-forget side effects at a named point.
- ``add_filter`` / ``apply_filters`` — pass a value through callbacks, each
  returning a (possibly) modified value.
- ``add_render`` / ``render_hook`` — collect HTML fragments to inject into a
  template region (e.g. the public footer).

Callbacks are ordered by ``priority`` (lower runs first; default 10). Each
callback is associated with a plugin (inferred from its module, or passed
explicitly); callbacks of a disabled plugin are skipped at call time, so plugins
can be toggled at runtime without a restart. Callbacks with ``plugin=None`` are
core and always run.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from types import FrameType

from django.utils.safestring import mark_safe


@dataclass
class _Hook:
    priority: int
    func: Callable
    plugin: str | None


_actions: dict[str, list[_Hook]] = defaultdict(list)
_filters: dict[str, list[_Hook]] = defaultdict(list)
_renders: dict[str, list[_Hook]] = defaultdict(list)


def _slug_from_module(module: str) -> str | None:
    return module.split(".")[1] if module.startswith("plugins.") else None


def _plugin_of(func: Callable) -> str | None:
    return _slug_from_module(getattr(func, "__module__", "") or "")


def _calling_plugin() -> str | None:
    """Infer the plugin slug from the module that is registering the hook.

    More robust than the callback's ``__module__``: a plugin may register an
    imported function or a ``functools.partial`` (whose module is elsewhere), but
    the registration call still happens from inside the ``plugins.<slug>`` module.
    """
    frame: FrameType | None = sys._getframe(1)
    while frame is not None:
        slug = _slug_from_module(frame.f_globals.get("__name__", ""))
        if slug is not None:
            return slug
        frame = frame.f_back
    return None


def _enabled(plugin: str | None) -> bool:
    if plugin is None:
        return True
    from .registry import is_plugin_enabled

    return is_plugin_enabled(plugin)


def _register(store: dict[str, list[_Hook]], name, func, priority, plugin):
    # Resolve the owning plugin: an explicit slug wins; otherwise infer from the
    # callback's module, then from the registering module (handles imported /
    # partial callbacks). None means "core" — always runs.
    owner = plugin if plugin is not None else _calling_plugin()

    def deco(fn: Callable) -> Callable:
        store[name].append(_Hook(priority, fn, owner if owner is not None else _plugin_of(fn)))
        store[name].sort(key=lambda h: h.priority)
        return fn

    return deco(func) if func is not None else deco


def add_action(name: str, func=None, *, priority: int = 10, plugin: str | None = None):
    return _register(_actions, name, func, priority, plugin)


def add_filter(name: str, func=None, *, priority: int = 10, plugin: str | None = None):
    return _register(_filters, name, func, priority, plugin)


def add_render(name: str, func=None, *, priority: int = 10, plugin: str | None = None):
    return _register(_renders, name, func, priority, plugin)


def do_action(name: str, *args, **kwargs) -> None:
    for hook in list(_actions.get(name, ())):
        if _enabled(hook.plugin):
            hook.func(*args, **kwargs)


def apply_filters(name: str, value, *args, **kwargs):
    for hook in list(_filters.get(name, ())):
        if _enabled(hook.plugin):
            value = hook.func(value, *args, **kwargs)
    return value


def render_hook(name: str, *args, **kwargs):
    """Collect HTML fragments from render callbacks for a template region.

    Output is marked safe: render callbacks are trusted (operator-installed plugin
    code), so a callback must escape any user-controlled data it interpolates.
    """
    parts = []
    for hook in list(_renders.get(name, ())):
        if _enabled(hook.plugin):
            out = hook.func(*args, **kwargs)
            if out:
                parts.append(str(out))
    return mark_safe("".join(parts))


def _reset_for_tests() -> None:
    """Clear all registered hooks (test helper only)."""
    _actions.clear()
    _filters.clear()
    _renders.clear()
