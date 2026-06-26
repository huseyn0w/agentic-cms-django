# django-parler ships no type stubs, so its TranslatableModel / TranslatableManager /
# TranslatableQuerySet / TranslatedFields all degrade to ``Any`` for mypy. That makes the
# django-stubs plugin unable to: type the dynamically-injected translated fields such as
# ``title``/``body`` (has-type), resolve managers built via ``TranslatableManager.from_queryset``
# (django-manager-missing / valid-type / misc), or reconcile the SchedulableMixin helpers with
# the concrete CharField / DateTimeField columns (assignment / var-annotated). These are
# third-party-stub gaps, not real type errors, so they are silenced for this module only —
# every other module stays fully type-checked.
# mypy: disable-error-code="has-type, assignment, django-manager-missing, var-annotated, valid-type, misc"
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from parler.managers import TranslatableManager, TranslatableQuerySet
from parler.models import TranslatableModel, TranslatedFields

from apps.seo.models import SeoFieldsMixin

from .utils import sanitize_html, unique_slugify


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        abstract = True


class Status(models.TextChoices):
    DRAFT = "draft", _("Draft")
    PUBLISHED = "published", _("Published")


class Category(TranslatableModel, TimeStampedModel):
    """Hierarchical taxonomy term (a category can have a parent category).

    ``name`` / ``description`` are translated per language; ``slug`` is shared so a
    category keeps one stable URL across languages (the language prefix differs).
    """

    translations = TranslatedFields(
        name=models.CharField(_("name"), max_length=100),
        description=models.TextField(_("description"), blank=True),
    )
    slug = models.SlugField(_("slug"), max_length=100, unique=True, blank=True)
    parent = models.ForeignKey(
        "self",
        verbose_name=_("parent"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )

    objects = TranslatableManager()

    class Meta:
        verbose_name = _("category")
        verbose_name_plural = _("categories")

    def __str__(self) -> str:
        return self.safe_translation_getter("name", any_language=True) or self.slug

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = unique_slugify(self, self.name, max_length=100)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("content:category", args=[self.slug])


class Tag(TranslatableModel, TimeStampedModel):
    translations = TranslatedFields(
        name=models.CharField(_("name"), max_length=50),
    )
    slug = models.SlugField(_("slug"), max_length=50, unique=True, blank=True)

    objects = TranslatableManager()

    class Meta:
        verbose_name = _("tag")
        verbose_name_plural = _("tags")

    def __str__(self) -> str:
        return self.safe_translation_getter("name", any_language=True) or self.slug

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = unique_slugify(self, self.name, max_length=50)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("content:tag", args=[self.slug])


class PublishableQuerySet(TranslatableQuerySet):
    def published(self) -> models.QuerySet:
        return self.filter(status=Status.PUBLISHED, published_at__lte=timezone.now())

    def drafts(self) -> models.QuerySet:
        return self.filter(status=Status.DRAFT)

    def due_for_publish(self) -> models.QuerySet:
        """Draft items whose scheduled time has arrived (ready to auto-publish)."""
        return self.filter(
            status=Status.DRAFT,
            scheduled_at__isnull=False,
            scheduled_at__lte=timezone.now(),
        )

    def editable_by(self, user) -> models.QuerySet:
        """Posts ``user`` may manage in the dashboard.

        Content managers (those who can delete any post — Editors/Admins) see
        everything; Authors/Contributors are scoped to their own posts. Returns a
        chainable queryset so callers can add ``.published()``/ordering/prefetch.
        """
        if user.has_perm("content.delete_post"):
            return self
        return self.filter(author=user)


PublishableManager = TranslatableManager.from_queryset(PublishableQuerySet)


class SoftDeleteQuerySet(PublishableQuerySet):
    """A publishable queryset that also understands soft-deletion."""

    def alive(self) -> models.QuerySet:
        return self.filter(deleted_at__isnull=True)

    def trashed(self) -> models.QuerySet:
        return self.filter(deleted_at__isnull=False)


_SoftDeleteManagerBase = TranslatableManager.from_queryset(SoftDeleteQuerySet)


class SoftDeleteManager(_SoftDeleteManagerBase):
    """Default manager that hides soft-deleted rows.

    ``Post.objects`` therefore never returns trashed items, so every existing
    public/admin/search/sitemap/feed query excludes them automatically without
    change. Trash views opt back in via ``with_trashed()`` / ``only_trashed()``.
    """

    def get_queryset(self) -> models.QuerySet:
        return super().get_queryset().alive()

    def with_trashed(self) -> models.QuerySet:
        return super().get_queryset()

    def only_trashed(self) -> models.QuerySet:
        return super().get_queryset().trashed()


class SoftDeleteModel(models.Model):
    """Mixin adding a ``deleted_at`` marker plus trash/restore transitions.

    The transitions are entity behaviour (cf. ``Comment.approve``) and persist
    only the marker via ``update_fields`` so the heavy ``save()`` override and the
    revision-snapshot signal stay no-ops on a soft-delete.
    """

    deleted_at = models.DateTimeField(_("deleted at"), null=True, blank=True)

    class Meta:
        abstract = True

    @property
    def is_trashed(self) -> bool:
        return self.deleted_at is not None

    def trash(self) -> None:
        """Soft-delete: hide from the default manager, keep the row + history."""
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])

    def restore(self) -> None:
        """Undo a soft-delete, bringing the row back into the default manager."""
        self.deleted_at = None
        self.save(update_fields=["deleted_at", "updated_at"])


class SchedulableMixin(models.Model):
    """Mixin for content that can be auto-published at a future time.

    The item stays a Draft (so it is invisible publicly) until ``scheduled_at``
    arrives and the ``publish_scheduled`` management command flips it. Requires the
    concrete model to expose ``status`` and ``published_at``.
    """

    scheduled_at = models.DateTimeField(
        _("scheduled for"),
        null=True,
        blank=True,
        help_text=_("Auto-publish at this time. Keep the status as Draft until then."),
    )

    class Meta:
        abstract = True

    @property
    def is_scheduled(self) -> bool:
        return self.status == Status.DRAFT and self.scheduled_at is not None

    def publish_scheduled(self) -> None:
        """Publish a due scheduled item, stamping its scheduled time as the date."""
        self.status = Status.PUBLISHED
        self.published_at = self.scheduled_at or timezone.now()
        self.scheduled_at = None
        self.save()


class Post(SeoFieldsMixin, SoftDeleteModel, SchedulableMixin, TranslatableModel, TimeStampedModel):
    translations = TranslatedFields(
        title=models.CharField(_("title"), max_length=200),
        excerpt=models.TextField(_("excerpt"), blank=True),
        body=models.TextField(_("body"), blank=True),
        meta_title=models.CharField(_("meta title"), max_length=70, blank=True),
        meta_description=models.CharField(_("meta description"), max_length=200, blank=True),
    )
    slug = models.SlugField(_("slug"), max_length=200, unique=True, blank=True)
    canonical_url = models.URLField(_("canonical URL"), blank=True)
    noindex = models.BooleanField(_("hide from search engines"), default=False)
    og_image = models.ImageField(_("share image"), upload_to="seo/", blank=True, null=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("author"),
        on_delete=models.SET_NULL,
        null=True,
        related_name="posts",
    )
    featured_image = models.ImageField(
        _("featured image"), upload_to="posts/", blank=True, null=True
    )
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.DRAFT
    )
    published_at = models.DateTimeField(_("published at"), null=True, blank=True)

    categories = models.ManyToManyField(
        Category, verbose_name=_("categories"), blank=True, related_name="posts"
    )
    tags = models.ManyToManyField(Tag, verbose_name=_("tags"), blank=True, related_name="posts")

    objects = SoftDeleteManager()

    class Meta:
        verbose_name = _("post")
        verbose_name_plural = _("posts")
        # nulls_last so unpublished (NULL published_at) posts sort after live ones,
        # including in the Django admin list under PostgreSQL.
        ordering = [models.F("published_at").desc(nulls_last=True), "-created_at"]
        permissions = [("publish_post", "Can publish posts")]

    def __str__(self) -> str:
        return self.safe_translation_getter("title", any_language=True) or self.slug

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = unique_slugify(self, self.title, max_length=200)
        # Sanitize all author-supplied HTML server-side, every save. These are
        # translated fields, so each language's body/excerpt is cleaned on its save.
        self.body = sanitize_html(self.body)
        self.excerpt = sanitize_html(self.excerpt)
        # Stamp publish time on first publish only. Re-publishing after an unpublish
        # deliberately keeps the original date so permalinks/feeds stay stable.
        if self.status == Status.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("content:post_detail", args=[self.slug])

    @property
    def is_published(self) -> bool:
        return self.status == Status.PUBLISHED and bool(
            self.published_at and self.published_at <= timezone.now()
        )

    def can_be_viewed_by(self, user) -> bool:
        """Who may see this post via its public URL.

        Published posts are public. Drafts are visible only to their author and to
        content managers — those who can delete any post (Editors/Admins). Authors
        and Contributors therefore see their own drafts but never each other's.
        """
        if self.is_published:
            return True
        if not user.is_authenticated:
            return False
        return user == self.author or user.has_perm("content.delete_post")

    def restore_revision(self, revision) -> None:
        """Roll this post's content back to ``revision`` (in its language).

        Saving re-sanitises and snapshots the restored state, so history is
        preserved rather than rewritten.
        """
        self.set_current_language(revision.language_code)
        self.title = revision.title
        self.body = revision.body
        self.save()

    def gate_publish_state(self, user) -> None:
        """Constrain this post's ``status`` to what ``user`` is allowed to set.

        Users without ``content.publish_post`` may not change the publish state:
        a new post is forced to DRAFT; an edited post keeps its stored status, so
        editing a post an Editor already published never silently unpublishes it
        (and a Contributor still can't publish a draft themselves). A no-op for
        users who may publish. Call before saving.
        """
        if user.has_perm("content.publish_post"):
            return
        if self.pk:
            # status is a shared (untranslated) field; fetch just it.
            self.status = Post.objects.only("status").get(pk=self.pk).status
        else:
            self.status = Status.DRAFT


class Page(SeoFieldsMixin, SoftDeleteModel, SchedulableMixin, TranslatableModel, TimeStampedModel):
    """A standalone, optionally hierarchical page (About, Contact, ...)."""

    translations = TranslatedFields(
        title=models.CharField(_("title"), max_length=200),
        body=models.TextField(_("body"), blank=True),
        meta_title=models.CharField(_("meta title"), max_length=70, blank=True),
        meta_description=models.CharField(_("meta description"), max_length=200, blank=True),
    )
    slug = models.SlugField(_("slug"), max_length=200, unique=True, blank=True)
    canonical_url = models.URLField(_("canonical URL"), blank=True)
    noindex = models.BooleanField(_("hide from search engines"), default=False)
    og_image = models.ImageField(_("share image"), upload_to="seo/", blank=True, null=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("author"),
        on_delete=models.SET_NULL,
        null=True,
        related_name="pages",
    )
    template = models.CharField(_("template"), max_length=100, default="default")
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.DRAFT
    )
    published_at = models.DateTimeField(_("published at"), null=True, blank=True)
    parent = models.ForeignKey(
        "self",
        verbose_name=_("parent"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )

    objects = SoftDeleteManager()

    class Meta:
        verbose_name = _("page")
        verbose_name_plural = _("pages")

    def __str__(self) -> str:
        return self.safe_translation_getter("title", any_language=True) or self.slug

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = unique_slugify(self, self.title, max_length=200)
        self.body = sanitize_html(self.body)
        if self.status == Status.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("content:page_detail", args=[self.slug])

    @property
    def is_published(self) -> bool:
        return self.status == Status.PUBLISHED and bool(
            self.published_at and self.published_at <= timezone.now()
        )

    def can_be_viewed_by(self, user) -> bool:
        """Published pages are public; drafts only to users who can edit pages."""
        if self.is_published:
            return True
        return user.is_authenticated and user.has_perm("content.change_page")

    def restore_revision(self, revision) -> None:
        """Roll this page's content back to ``revision`` (in its language)."""
        self.set_current_language(revision.language_code)
        self.title = revision.title
        self.body = revision.body
        self.save()


class Service(SeoFieldsMixin, SchedulableMixin, TranslatableModel, TimeStampedModel):
    """A GEO-optimized service page — the format answer engines quote.

    Pairs a crisp definitional ``summary`` with a rich ``description``, citable
    facts (``price``, ``area_served``) and a Q&A ``faq`` block. The public template
    and the Service + FAQPage JSON-LD are built from these so an assistant can
    extract "what you offer", "where", "how much" and answer common questions.
    """

    translations = TranslatedFields(
        title=models.CharField(_("title"), max_length=200),
        summary=models.CharField(
            _("summary"),
            max_length=300,
            blank=True,
            help_text=_("One or two plain sentences answering “what is this service?”."),
        ),
        description=models.TextField(_("description"), blank=True),
        area_served=models.CharField(
            _("area served"),
            max_length=200,
            blank=True,
            help_text=_("e.g. “United States” or “Berlin and surrounding areas”."),
        ),
        faq=models.TextField(
            _("FAQ"),
            blank=True,
            help_text=_("Q&A blocks. One per pair:\nQ: question\nA: answer"),
        ),
        meta_title=models.CharField(_("meta title"), max_length=70, blank=True),
        meta_description=models.CharField(_("meta description"), max_length=200, blank=True),
    )
    slug = models.SlugField(_("slug"), max_length=200, unique=True, blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("author"),
        on_delete=models.SET_NULL,
        null=True,
        related_name="services",
    )
    price = models.CharField(
        _("price"),
        max_length=100,
        blank=True,
        help_text=_("Freeform, e.g. “From $499” or “€90/hour”."),
    )
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.DRAFT
    )
    published_at = models.DateTimeField(_("published at"), null=True, blank=True)
    canonical_url = models.URLField(_("canonical URL"), blank=True)
    noindex = models.BooleanField(_("hide from search engines"), default=False)
    og_image = models.ImageField(_("share image"), upload_to="seo/", blank=True, null=True)

    objects = PublishableManager()

    class Meta:
        verbose_name = _("service")
        verbose_name_plural = _("services")

    def __str__(self) -> str:
        return self.safe_translation_getter("title", any_language=True) or self.slug

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = unique_slugify(self, self.title, max_length=200)
        self.description = sanitize_html(self.description)
        if self.status == Status.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("content:service_detail", args=[self.slug])

    @property
    def body(self) -> str:
        """Alias so SEO/llms helpers that read ``body`` work for services too."""
        return self.description

    def seo_description(self) -> str:
        # meta_description -> summary -> (mixin) stripped description body.
        return (
            (self.meta_description or "").strip()
            or (self.summary or "").strip()
            or super().seo_description()
        )

    @property
    def is_published(self) -> bool:
        return self.status == Status.PUBLISHED and bool(
            self.published_at and self.published_at <= timezone.now()
        )

    def can_be_viewed_by(self, user) -> bool:
        if self.is_published:
            return True
        return user.is_authenticated and user.has_perm("content.change_service")

    def faq_items(self) -> list[tuple[str, str]]:
        """Parse the FAQ textarea into (question, answer) pairs.

        Format is alternating ``Q:`` / ``A:`` lines; anything else is ignored.
        """
        items: list[tuple[str, str]] = []
        question: str | None = None
        for raw in self.faq.splitlines():
            line = raw.strip()
            if line[:2].lower() == "q:":
                question = line[2:].strip()
            elif line[:2].lower() == "a:" and question:
                items.append((question, line[2:].strip()))
                question = None
        return items


class Revision(TimeStampedModel):
    """Immutable snapshot of one language's post/page body taken on each save."""

    language_code = models.CharField(_("language"), max_length=15, default="en")
    title = models.CharField(_("title"), max_length=200)
    body = models.TextField(_("body"), blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("author"),
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
    )

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.title} [{self.language_code}] @ {self.created_at:%Y-%m-%d %H:%M}"


class PostRevision(Revision):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="revisions")


class PageRevision(Revision):
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="revisions")


class Like(models.Model):
    """An authenticated reader's like on a post.

    Identity is the user, so a like is idempotent (one per user per post via the
    unique constraint) and a guest must sign in first. Deleting a like row is an
    unlike, so the relation doubles as a toggle.
    """

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="likes"
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("like")
        verbose_name_plural = _("likes")
        constraints = [
            models.UniqueConstraint(fields=["post", "user"], name="unique_post_like_per_user")
        ]

    def __str__(self) -> str:
        return f"{self.user_id} ♥ {self.post_id}"
