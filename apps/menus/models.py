from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _


class Menu(models.Model):
    """A named, orderable navigation menu referenced by its ``slug``.

    Templates render a menu by slug via ``{% menu_items "primary" as items %}``;
    the public shell uses ``primary`` (header) and ``footer`` when they exist and
    falls back to its built-in links otherwise.
    """

    name = models.CharField(_("name"), max_length=100)
    slug = models.SlugField(
        _("slug"),
        max_length=100,
        unique=True,
        help_text=_("Referenced in templates, e.g. “primary” or “footer”."),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("menu")
        verbose_name_plural = _("menus")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class LinkType(models.TextChoices):
    CUSTOM = "custom", _("Custom URL")
    POST = "post", _("Post")
    PAGE = "page", _("Page")
    CATEGORY = "category", _("Category")


class MenuItem(models.Model):
    """One entry in a menu, linking to a post/page/category or a custom URL.

    The ``label`` is optional: for content links it falls back to the linked
    object's (translated) title, so blog/page entries localise automatically.
    """

    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name="items")
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        help_text=_("Nest this item under a top-level item (one level deep)."),
    )
    label = models.CharField(
        _("label"),
        max_length=80,
        blank=True,
        help_text=_("Leave blank to use the linked item's title."),
    )
    link_type = models.CharField(
        _("links to"), max_length=10, choices=LinkType.choices, default=LinkType.CUSTOM
    )
    url = models.CharField(_("custom URL"), max_length=300, blank=True)
    post = models.ForeignKey(
        "content.Post", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    page = models.ForeignKey(
        "content.Page", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    category = models.ForeignKey(
        "content.Category", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    position = models.PositiveIntegerField(_("position"), default=0)

    class Meta:
        verbose_name = _("menu item")
        verbose_name_plural = _("menu items")
        ordering = ["position", "id"]

    def __str__(self) -> str:
        return self.get_label()

    def linked_object(self):
        """The referenced content object for this item's link type, or None."""
        return {
            LinkType.POST: self.post,
            LinkType.PAGE: self.page,
            LinkType.CATEGORY: self.category,
        }.get(self.link_type)

    def get_url(self) -> str:
        obj = self.linked_object()
        if obj is not None:
            return obj.get_absolute_url()
        return self.url or "/"

    def get_label(self) -> str:
        if self.label:
            return self.label
        obj = self.linked_object()
        return str(obj) if obj is not None else (self.url or "")
