"""Accessibility helpers for dashboard form rendering (U6).

``aria_field`` re-renders a bound field with ``aria-invalid`` and an
``aria-describedby`` that points at its error and help-text elements, so screen
readers announce validation state and guidance. The matching ids are emitted by
``dashboard/_field.html``.
"""

from __future__ import annotations

from django import template

register = template.Library()


@register.filter
def aria_field(field, testid: str = ""):
    """Render ``field``'s widget with aria-invalid / aria-describedby wired up.

    An optional ``testid`` adds a stable ``data-testid`` to the widget so the
    Playwright end-to-end suite can target form controls without depending on
    label text or CSS classes (which churn with styling).
    """
    attrs: dict[str, str] = {}
    described_by: list[str] = []
    if field.errors:
        attrs["aria-invalid"] = "true"
        described_by.append(f"{field.auto_id}_error")
    if field.help_text:
        described_by.append(f"{field.auto_id}_help")
    if described_by:
        attrs["aria-describedby"] = " ".join(described_by)
    if testid:
        attrs["data-testid"] = testid
    return field.as_widget(attrs=attrs)
