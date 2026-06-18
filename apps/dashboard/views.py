from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Count, QuerySet
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)
from parler.views import TranslatableModelFormMixin

from apps.comments.models import Comment, CommentStatus
from apps.content.models import Category, Page, Post, Service, Status, Tag
from apps.core.models import SiteSettings
from apps.media.models import MediaAsset
from apps.plugins import registry as plugins
from apps.seo.models import SeoSettings
from apps.themes import registry as themes

from .forms import (
    CategoryForm,
    PageForm,
    PostForm,
    SeoSettingsForm,
    ServiceForm,
    SiteSettingsForm,
    TagForm,
    UserRoleForm,
)
from .mixins import AdminAccessMixin

User = get_user_model()


class DashboardTranslatableFormMixin(TranslatableModelFormMixin):
    """parler editing mixin that rejects unknown ``?language=`` codes.

    parler normalises the query parameter but does not validate it against the
    configured languages, so a hand-crafted ``?language=xx`` would silently create
    an orphan translation row. Clamp it to a configured language instead.
    """

    def get_language(self):
        language = super().get_language()
        valid = {code for code, _name in settings.LANGUAGES}
        return language if language in valid else self.get_default_language()


class SectionMixin:
    """Provide `section` (active nav) and `heading` to admin templates."""

    section: str | None = None
    heading: str | None = None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["section"] = self.section
        ctx["heading"] = self.heading
        return ctx


# --------------------------------------------------------------------------- #
# Dashboard home
# --------------------------------------------------------------------------- #
class DashboardHomeView(AdminAccessMixin, SectionMixin, TemplateView):
    template_name = "dashboard/home.html"
    section = "home"
    heading = "Dashboard"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["stats"] = {
            "posts": Post.objects.count(),
            "pages": Page.objects.count(),
            "media": MediaAsset.objects.count(),
            "users": User.objects.count(),
        }
        # Non-managers only see their own recent posts (matches what they can edit).
        recent = Post.objects.select_related("author")
        if not self.request.user.has_perm("content.delete_post"):
            recent = recent.filter(author=self.request.user)
        ctx["recent_posts"] = recent[:6]
        return ctx


# --------------------------------------------------------------------------- #
# Posts (owner-scoped for non-managers)
# --------------------------------------------------------------------------- #
class PostScopeMixin:
    """Restrict posts to those the user may manage.

    Managers (users who can delete any post — Editors/Admins) see everything;
    Authors/Contributors see only their own.
    """

    def get_queryset(self) -> QuerySet:
        qs = Post.objects.select_related("author")
        if not self.request.user.has_perm("content.delete_post"):
            qs = qs.filter(author=self.request.user)
        return qs


class PostListView(AdminAccessMixin, SectionMixin, PostScopeMixin, ListView):
    permission_required = ("accounts.access_admin", "content.view_post")
    template_name = "dashboard/post_list.html"
    context_object_name = "posts"
    paginate_by = 20
    section = "posts"
    heading = "Posts"

    def get_queryset(self) -> QuerySet:
        qs = super().get_queryset()
        status = self.request.GET.get("status")
        if status in Status.values:
            qs = qs.filter(status=status)
        search = self.request.GET.get("q")
        if search:
            # title is translated (parler) -> search through the translation table.
            qs = qs.filter(translations__title__icontains=search).distinct()
        return qs


class PublishGatingMixin:
    """Users without `publish_post` cannot change a post's publish state.

    New posts they create are drafts; when they edit an existing post its stored
    status is preserved — so editing a post an Editor already published does NOT
    silently unpublish it, and they still can't publish a draft themselves.
    """

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["can_publish"] = self.request.user.has_perm("content.publish_post")
        return kwargs

    def form_valid(self, form):
        if not self.request.user.has_perm("content.publish_post"):
            if form.instance.pk:
                # status is a shared (untranslated) field; fetch just it.
                form.instance.status = Post.objects.only("status").get(pk=form.instance.pk).status
            else:
                form.instance.status = Status.DRAFT
        return super().form_valid(form)


class PostCreateView(
    AdminAccessMixin, SectionMixin, PublishGatingMixin, DashboardTranslatableFormMixin, CreateView
):
    permission_required = ("accounts.access_admin", "content.add_post")
    model = Post
    form_class = PostForm
    template_name = "dashboard/post_form.html"
    success_url = reverse_lazy("dashboard:post_list")
    section = "posts"
    heading = "New post"

    def form_valid(self, form):
        form.instance.author = self.request.user
        messages.success(self.request, "Post created.")
        return super().form_valid(form)


class PostUpdateView(
    AdminAccessMixin,
    SectionMixin,
    PostScopeMixin,
    PublishGatingMixin,
    DashboardTranslatableFormMixin,
    UpdateView,
):
    permission_required = ("accounts.access_admin", "content.change_post")
    form_class = PostForm
    template_name = "dashboard/post_form.html"
    success_url = reverse_lazy("dashboard:post_list")
    section = "posts"
    heading = "Edit post"

    def form_valid(self, form):
        messages.success(self.request, "Post updated.")
        return super().form_valid(form)


class PostDeleteView(AdminAccessMixin, PostScopeMixin, DeleteView):
    permission_required = ("accounts.access_admin", "content.delete_post")
    success_url = reverse_lazy("dashboard:post_list")
    http_method_names = ["post"]

    def form_valid(self, form):
        messages.success(self.request, "Post deleted.")
        return super().form_valid(form)


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
class PageListView(AdminAccessMixin, SectionMixin, ListView):
    permission_required = ("accounts.access_admin", "content.view_page")
    template_name = "dashboard/page_list.html"
    context_object_name = "pages"
    paginate_by = 20
    section = "pages"
    heading = "Pages"
    # Models lost their Meta ordering (it referenced now-translated fields), so
    # order on a shared field here for stable pagination.
    queryset = Page.objects.select_related("author").order_by("-created_at")


class PageCreateView(AdminAccessMixin, SectionMixin, DashboardTranslatableFormMixin, CreateView):
    permission_required = ("accounts.access_admin", "content.add_page")
    model = Page
    form_class = PageForm
    template_name = "dashboard/page_form.html"
    success_url = reverse_lazy("dashboard:page_list")
    section = "pages"
    heading = "New page"

    def form_valid(self, form):
        form.instance.author = self.request.user
        messages.success(self.request, "Page created.")
        return super().form_valid(form)


class PageUpdateView(AdminAccessMixin, SectionMixin, DashboardTranslatableFormMixin, UpdateView):
    permission_required = ("accounts.access_admin", "content.change_page")
    model = Page
    form_class = PageForm
    template_name = "dashboard/page_form.html"
    success_url = reverse_lazy("dashboard:page_list")
    section = "pages"
    heading = "Edit page"

    def form_valid(self, form):
        messages.success(self.request, "Page updated.")
        return super().form_valid(form)


class PageDeleteView(AdminAccessMixin, DeleteView):
    permission_required = ("accounts.access_admin", "content.delete_page")
    model = Page
    success_url = reverse_lazy("dashboard:page_list")
    http_method_names = ["post"]


# --------------------------------------------------------------------------- #
# Services (GEO)
# --------------------------------------------------------------------------- #
class ServiceListView(AdminAccessMixin, SectionMixin, ListView):
    permission_required = ("accounts.access_admin", "content.view_service")
    template_name = "dashboard/service_list.html"
    context_object_name = "services"
    paginate_by = 20
    section = "services"
    heading = "Services"
    queryset = Service.objects.select_related("author").order_by("-created_at")


class ServiceCreateView(AdminAccessMixin, SectionMixin, DashboardTranslatableFormMixin, CreateView):
    permission_required = ("accounts.access_admin", "content.add_service")
    model = Service
    form_class = ServiceForm
    template_name = "dashboard/service_form.html"
    success_url = reverse_lazy("dashboard:service_list")
    section = "services"
    heading = "New service"

    def form_valid(self, form):
        form.instance.author = self.request.user
        messages.success(self.request, "Service created.")
        return super().form_valid(form)


class ServiceUpdateView(AdminAccessMixin, SectionMixin, DashboardTranslatableFormMixin, UpdateView):
    permission_required = ("accounts.access_admin", "content.change_service")
    model = Service
    form_class = ServiceForm
    template_name = "dashboard/service_form.html"
    success_url = reverse_lazy("dashboard:service_list")
    section = "services"
    heading = "Edit service"

    def form_valid(self, form):
        messages.success(self.request, "Service updated.")
        return super().form_valid(form)


class ServiceDeleteView(AdminAccessMixin, DeleteView):
    permission_required = ("accounts.access_admin", "content.delete_service")
    model = Service
    success_url = reverse_lazy("dashboard:service_list")
    http_method_names = ["post"]


# --------------------------------------------------------------------------- #
# Taxonomy: categories & tags
# --------------------------------------------------------------------------- #
class CategoryListView(AdminAccessMixin, SectionMixin, ListView):
    permission_required = ("accounts.access_admin", "content.view_category")
    template_name = "dashboard/category_list.html"
    context_object_name = "categories"
    section = "categories"
    heading = "Categories"
    queryset = (
        Category.objects.select_related("parent")
        .annotate(post_count=Count("posts"))
        .order_by("slug")
    )


class CategoryCreateView(
    AdminAccessMixin, SectionMixin, DashboardTranslatableFormMixin, CreateView
):
    permission_required = ("accounts.access_admin", "content.add_category")
    model = Category
    form_class = CategoryForm
    template_name = "dashboard/taxonomy_form.html"
    success_url = reverse_lazy("dashboard:category_list")
    section = "categories"
    heading = "New category"


class CategoryUpdateView(
    AdminAccessMixin, SectionMixin, DashboardTranslatableFormMixin, UpdateView
):
    permission_required = ("accounts.access_admin", "content.change_category")
    model = Category
    form_class = CategoryForm
    template_name = "dashboard/taxonomy_form.html"
    success_url = reverse_lazy("dashboard:category_list")
    section = "categories"
    heading = "Edit category"


class CategoryDeleteView(AdminAccessMixin, DeleteView):
    permission_required = ("accounts.access_admin", "content.delete_category")
    model = Category
    success_url = reverse_lazy("dashboard:category_list")
    http_method_names = ["post"]


class TagListView(AdminAccessMixin, SectionMixin, ListView):
    permission_required = ("accounts.access_admin", "content.view_tag")
    template_name = "dashboard/tag_list.html"
    context_object_name = "tags"
    section = "tags"
    heading = "Tags"
    queryset = Tag.objects.annotate(post_count=Count("posts")).order_by("slug")


class TagCreateView(AdminAccessMixin, SectionMixin, DashboardTranslatableFormMixin, CreateView):
    permission_required = ("accounts.access_admin", "content.add_tag")
    model = Tag
    form_class = TagForm
    template_name = "dashboard/taxonomy_form.html"
    success_url = reverse_lazy("dashboard:tag_list")
    section = "tags"
    heading = "New tag"


class TagUpdateView(AdminAccessMixin, SectionMixin, DashboardTranslatableFormMixin, UpdateView):
    permission_required = ("accounts.access_admin", "content.change_tag")
    model = Tag
    form_class = TagForm
    template_name = "dashboard/taxonomy_form.html"
    success_url = reverse_lazy("dashboard:tag_list")
    section = "tags"
    heading = "Edit tag"


class TagDeleteView(AdminAccessMixin, DeleteView):
    permission_required = ("accounts.access_admin", "content.delete_tag")
    model = Tag
    success_url = reverse_lazy("dashboard:tag_list")
    http_method_names = ["post"]


# --------------------------------------------------------------------------- #
# Users & roles
# --------------------------------------------------------------------------- #
class UserListView(AdminAccessMixin, SectionMixin, ListView):
    permission_required = ("accounts.access_admin", "accounts.manage_users")
    template_name = "dashboard/user_list.html"
    context_object_name = "users"
    paginate_by = 25
    section = "users"
    heading = "Users"
    queryset = User.objects.prefetch_related("groups").order_by("username")


class UserUpdateView(AdminAccessMixin, SectionMixin, UpdateView):
    permission_required = ("accounts.access_admin", "accounts.manage_users")
    model = User
    form_class = UserRoleForm
    template_name = "dashboard/user_form.html"
    success_url = reverse_lazy("dashboard:user_list")
    section = "users"
    heading = "Edit user"

    def dispatch(self, request, *args, **kwargs):
        # Guard against self-lockout: managers can't change their own roles or
        # active state here (would let them drop their own admin access).
        if request.user.is_authenticated and self.get_object() == request.user:
            messages.error(request, "You can't edit your own roles here.")
            return redirect("dashboard:user_list")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "User updated.")
        return super().form_valid(form)


# --------------------------------------------------------------------------- #
# Appearance: themes
# --------------------------------------------------------------------------- #
class ThemeListView(AdminAccessMixin, SectionMixin, TemplateView):
    permission_required = ("accounts.access_admin", "accounts.manage_settings")
    template_name = "dashboard/themes.html"
    section = "appearance"
    heading = "Appearance"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["themes"] = themes.get_available_themes()
        ctx["active_slug"] = themes.get_active_theme_slug()
        return ctx


class ThemeActivateView(AdminAccessMixin, View):
    permission_required = ("accounts.access_admin", "accounts.manage_settings")
    http_method_names = ["post"]

    def post(self, request, slug: str):
        if themes.activate_theme(slug):
            messages.success(request, f"Theme “{slug}” activated.")
        else:
            messages.error(request, "Unknown theme.")
        return redirect("dashboard:themes")


# --------------------------------------------------------------------------- #
# Plugins
# --------------------------------------------------------------------------- #
class PluginListView(AdminAccessMixin, SectionMixin, TemplateView):
    permission_required = ("accounts.access_admin", "accounts.manage_settings")
    template_name = "dashboard/plugins.html"
    section = "plugins"
    heading = "Plugins"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["plugins"] = [
            {"info": info, "enabled": plugins.is_plugin_enabled(info.slug)}
            for info in plugins.get_installed_plugins()
        ]
        return ctx


class PluginToggleView(AdminAccessMixin, View):
    permission_required = ("accounts.access_admin", "accounts.manage_settings")
    http_method_names = ["post"]

    def post(self, request, slug: str):
        now_enabled = not plugins.is_plugin_enabled(slug)
        if plugins.set_enabled(slug, now_enabled):
            messages.success(
                request, f"Plugin “{slug}” {'enabled' if now_enabled else 'disabled'}."
            )
        else:
            messages.error(request, "Unknown plugin.")
        return redirect("dashboard:plugins")


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #
class SettingsView(AdminAccessMixin, SectionMixin, UpdateView):
    permission_required = ("accounts.access_admin", "accounts.manage_settings")
    form_class = SiteSettingsForm
    template_name = "dashboard/settings.html"
    success_url = reverse_lazy("dashboard:settings")
    section = "settings"
    heading = "Settings"

    def get_object(self, queryset=None) -> SiteSettings:
        return SiteSettings.load()

    def form_valid(self, form):
        messages.success(self.request, "Settings saved.")
        return super().form_valid(form)


class SeoSettingsView(AdminAccessMixin, SectionMixin, UpdateView):
    permission_required = ("accounts.access_admin", "accounts.manage_settings")
    form_class = SeoSettingsForm
    template_name = "dashboard/seo_settings.html"
    success_url = reverse_lazy("dashboard:seo_settings")
    section = "seo"
    heading = "SEO"

    def get_object(self, queryset=None) -> SeoSettings:
        return SeoSettings.load()

    def form_valid(self, form):
        messages.success(self.request, "SEO settings saved.")
        return super().form_valid(form)


# --------------------------------------------------------------------------- #
# Comment moderation
# --------------------------------------------------------------------------- #
class CommentListView(AdminAccessMixin, SectionMixin, ListView):
    permission_required = ("accounts.access_admin", "comments.moderate_comment")
    template_name = "dashboard/comment_list.html"
    context_object_name = "comments"
    paginate_by = 30
    section = "comments"
    heading = "Comments"

    def get_queryset(self) -> QuerySet:
        qs = Comment.objects.select_related("post", "user").order_by("-created_at")
        self.status = self.request.GET.get("status")
        if self.status in CommentStatus.values:
            qs = qs.filter(status=self.status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status"] = self.status
        ctx["statuses"] = CommentStatus.choices
        ctx["pending_count"] = Comment.objects.pending().count()
        return ctx


class CommentModerateView(AdminAccessMixin, View):
    permission_required = ("accounts.access_admin", "comments.moderate_comment")
    http_method_names = ["post"]

    _ACTIONS = {
        "approve": (CommentStatus.APPROVED, "Comment approved."),
        "spam": (CommentStatus.SPAM, "Comment marked as spam."),
    }

    def post(self, request, pk: int, action: str):
        comment = get_object_or_404(Comment, pk=pk)
        if action == "delete":
            comment.delete()
            messages.success(request, "Comment deleted.")
        elif action in self._ACTIONS:
            status, message = self._ACTIONS[action]
            comment.status = status
            comment.save(update_fields=["status"])
            messages.success(request, message)
        else:
            raise Http404
        return redirect("dashboard:comment_list")
