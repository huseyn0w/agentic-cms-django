from __future__ import annotations

import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.template.defaultfilters import pluralize
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

from apps.content.models import Category, Page, Post, Service, Tag
from apps.menus.models import Menu, MenuItem

from . import services
from .forms import (
    CategoryForm,
    MenuForm,
    MenuItemForm,
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


class MediaPickerContextMixin:
    """Expose recent library images to a content editor for the in-editor picker.

    Only populated for users who may view media, so the picker stays hidden from
    those without media access.
    """

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.user.has_perm("media.view_mediaasset"):
            ctx["media_images"] = services.recent_media_images()
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
        ctx["stats"] = services.dashboard_stats()
        ctx["recent_posts"] = services.recent_posts(self.request.user)
        return ctx


# --------------------------------------------------------------------------- #
# Posts (owner-scoped for non-managers)
# --------------------------------------------------------------------------- #
class PostScopeMixin:
    """Restrict edit/delete to posts the user may manage (Authors see only their own)."""

    def get_queryset(self):
        return services.editable_posts(self.request.user)


class PostListView(AdminAccessMixin, SectionMixin, ListView):
    permission_required = ("accounts.access_admin", "content.view_post")
    template_name = "dashboard/post_list.html"
    context_object_name = "posts"
    paginate_by = 20
    section = "posts"
    heading = "Posts"

    def get_queryset(self):
        return services.list_posts(
            self.request.user,
            status=self.request.GET.get("status"),
            search=self.request.GET.get("q"),
        )


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
        form.instance.gate_publish_state(self.request.user)
        return super().form_valid(form)


class PostCreateView(
    AdminAccessMixin,
    SectionMixin,
    MediaPickerContextMixin,
    PublishGatingMixin,
    DashboardTranslatableFormMixin,
    CreateView,
):
    permission_required = ("accounts.access_admin", "content.add_post")
    model = Post
    form_class = PostForm
    template_name = "dashboard/post_form.html"
    success_url = reverse_lazy("dashboard:post_list")
    section = "posts"
    heading = "New post"

    def form_valid(self, form):
        services.prepare_new_post(form.instance, self.request.user)
        messages.success(self.request, "Post created.")
        return super().form_valid(form)


class PostUpdateView(
    AdminAccessMixin,
    SectionMixin,
    MediaPickerContextMixin,
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


class PostDeleteView(AdminAccessMixin, View):
    """Soft-delete (trash) a post; restore/permanent-delete live in the trash view."""

    permission_required = ("accounts.access_admin", "content.delete_post")
    http_method_names = ["post"]

    def post(self, request, pk: int):
        services.trash_post(request.user, pk)
        messages.success(request, "Post moved to trash.")
        return redirect("dashboard:post_list")


class PostBulkActionView(AdminAccessMixin, View):
    """Apply a bulk action to the selected posts (currently: move to trash)."""

    permission_required = ("accounts.access_admin", "content.delete_post")
    http_method_names = ["post"]

    def post(self, request):
        ids = request.POST.getlist("ids")
        if request.POST.get("action") == "trash" and ids:
            count = services.bulk_trash_posts(request.user, ids)
            if count:
                messages.success(request, f"{count} post{pluralize(count)} moved to trash.")
            else:
                messages.info(request, "No posts were trashed.")
        return redirect("dashboard:post_list")


class PostTrashListView(AdminAccessMixin, SectionMixin, ListView):
    permission_required = ("accounts.access_admin", "content.delete_post")
    template_name = "dashboard/post_trash.html"
    context_object_name = "posts"
    paginate_by = 20
    section = "posts"
    heading = "Trash"

    def get_queryset(self):
        return services.list_trashed_posts(self.request.user)


class PostRestoreView(AdminAccessMixin, View):
    permission_required = ("accounts.access_admin", "content.delete_post")
    http_method_names = ["post"]

    def post(self, request, pk: int):
        services.restore_post(request.user, pk)
        messages.success(request, "Post restored.")
        return redirect("dashboard:post_trash")


class PostDestroyView(AdminAccessMixin, View):
    permission_required = ("accounts.access_admin", "content.delete_post")
    http_method_names = ["post"]

    def post(self, request, pk: int):
        services.permanently_delete_post(request.user, pk)
        messages.success(request, "Post permanently deleted.")
        return redirect("dashboard:post_trash")


class PostRevisionListView(AdminAccessMixin, SectionMixin, TemplateView):
    permission_required = ("accounts.access_admin", "content.change_post")
    template_name = "dashboard/revisions.html"
    section = "posts"
    heading = "Revision history"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            services.post_revisions_context(
                self.request.user, self.kwargs["pk"], self.request.GET.get("revision")
            )
        )
        return ctx


class PostRevisionRestoreView(AdminAccessMixin, View):
    permission_required = ("accounts.access_admin", "content.change_post")
    http_method_names = ["post"]

    def post(self, request, pk: int, revision_pk: int):
        services.restore_post_revision(request.user, pk, revision_pk)
        messages.success(request, "Revision restored.")
        return redirect("dashboard:post_edit", pk=pk)


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

    def get_queryset(self):
        return services.list_pages()


class PageCreateView(
    AdminAccessMixin,
    SectionMixin,
    MediaPickerContextMixin,
    DashboardTranslatableFormMixin,
    CreateView,
):
    permission_required = ("accounts.access_admin", "content.add_page")
    model = Page
    form_class = PageForm
    template_name = "dashboard/page_form.html"
    success_url = reverse_lazy("dashboard:page_list")
    section = "pages"
    heading = "New page"

    def form_valid(self, form):
        services.prepare_new_page(form.instance, self.request.user)
        messages.success(self.request, "Page created.")
        return super().form_valid(form)


class PageUpdateView(
    AdminAccessMixin,
    SectionMixin,
    MediaPickerContextMixin,
    DashboardTranslatableFormMixin,
    UpdateView,
):
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


class PageDeleteView(AdminAccessMixin, View):
    """Soft-delete (trash) a page."""

    permission_required = ("accounts.access_admin", "content.delete_page")
    http_method_names = ["post"]

    def post(self, request, pk: int):
        services.trash_page(pk)
        messages.success(request, "Page moved to trash.")
        return redirect("dashboard:page_list")


class PageTrashListView(AdminAccessMixin, SectionMixin, ListView):
    permission_required = ("accounts.access_admin", "content.delete_page")
    template_name = "dashboard/page_trash.html"
    context_object_name = "pages"
    paginate_by = 20
    section = "pages"
    heading = "Trash"

    def get_queryset(self):
        return services.list_trashed_pages()


class PageRestoreView(AdminAccessMixin, View):
    permission_required = ("accounts.access_admin", "content.delete_page")
    http_method_names = ["post"]

    def post(self, request, pk: int):
        services.restore_page(pk)
        messages.success(request, "Page restored.")
        return redirect("dashboard:page_trash")


class PageDestroyView(AdminAccessMixin, View):
    permission_required = ("accounts.access_admin", "content.delete_page")
    http_method_names = ["post"]

    def post(self, request, pk: int):
        services.permanently_delete_page(pk)
        messages.success(request, "Page permanently deleted.")
        return redirect("dashboard:page_trash")


class PageRevisionListView(AdminAccessMixin, SectionMixin, TemplateView):
    permission_required = ("accounts.access_admin", "content.change_page")
    template_name = "dashboard/revisions.html"
    section = "pages"
    heading = "Revision history"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            services.page_revisions_context(self.kwargs["pk"], self.request.GET.get("revision"))
        )
        return ctx


class PageRevisionRestoreView(AdminAccessMixin, View):
    permission_required = ("accounts.access_admin", "content.change_page")
    http_method_names = ["post"]

    def post(self, request, pk: int, revision_pk: int):
        services.restore_page_revision(pk, revision_pk)
        messages.success(request, "Revision restored.")
        return redirect("dashboard:page_edit", pk=pk)


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

    def get_queryset(self):
        return services.list_services()


class ServiceCreateView(
    AdminAccessMixin,
    SectionMixin,
    MediaPickerContextMixin,
    DashboardTranslatableFormMixin,
    CreateView,
):
    permission_required = ("accounts.access_admin", "content.add_service")
    model = Service
    form_class = ServiceForm
    template_name = "dashboard/service_form.html"
    success_url = reverse_lazy("dashboard:service_list")
    section = "services"
    heading = "New service"

    def form_valid(self, form):
        services.prepare_new_service(form.instance, self.request.user)
        messages.success(self.request, "Service created.")
        return super().form_valid(form)


class ServiceUpdateView(
    AdminAccessMixin,
    SectionMixin,
    MediaPickerContextMixin,
    DashboardTranslatableFormMixin,
    UpdateView,
):
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


# django-stubs flags DeleteView's DeletionMixin/BaseDetailView `object` MRO clash (false positive).
class ServiceDeleteView(AdminAccessMixin, DeleteView):  # type: ignore[misc]
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

    def get_queryset(self):
        return services.list_categories()


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


class CategoryDeleteView(AdminAccessMixin, DeleteView):  # type: ignore[misc]
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

    def get_queryset(self):
        return services.list_tags()


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


class TagDeleteView(AdminAccessMixin, DeleteView):  # type: ignore[misc]
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

    def get_queryset(self):
        return services.list_users()


class UserUpdateView(AdminAccessMixin, SectionMixin, UpdateView):
    permission_required = ("accounts.access_admin", "accounts.manage_users")
    model = User
    form_class = UserRoleForm
    template_name = "dashboard/user_form.html"
    success_url = reverse_lazy("dashboard:user_list")
    section = "users"
    heading = "Edit user"

    def get_object(self, queryset=None):
        return services.get_user(self.kwargs["pk"])

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
        ctx["themes"] = services.available_themes()
        ctx["active_slug"] = services.active_theme_slug()
        return ctx


class ThemeActivateView(AdminAccessMixin, View):
    permission_required = ("accounts.access_admin", "accounts.manage_settings")
    http_method_names = ["post"]

    def post(self, request, slug: str):
        if services.activate_theme(slug):
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
        ctx["plugins"] = services.installed_plugins_with_state()
        return ctx


class PluginToggleView(AdminAccessMixin, View):
    permission_required = ("accounts.access_admin", "accounts.manage_settings")
    http_method_names = ["post"]

    def post(self, request, slug: str):
        now_enabled = not services.is_plugin_enabled(slug)
        if services.set_plugin_enabled(slug, now_enabled):
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

    def get_object(self, queryset=None):
        return services.load_site_settings()

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

    def get_object(self, queryset=None):
        return services.load_seo_settings()

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

    def get_queryset(self):
        self.status = self.request.GET.get("status")
        return services.list_comments(self.status)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status"] = self.status
        ctx["statuses"] = services.comment_status_choices()
        ctx["pending_count"] = services.pending_comment_count()
        return ctx


class CommentModerateView(AdminAccessMixin, View):
    permission_required = ("accounts.access_admin", "comments.moderate_comment")
    http_method_names = ["post"]

    def post(self, request, pk: int, action: str):
        comment = services.get_comment(pk)
        try:
            message = services.moderate_comment(comment, action)
        except ValueError as exc:
            raise Http404 from exc
        messages.success(request, message)
        return redirect("dashboard:comment_list")


# --------------------------------------------------------------------------- #
# Menus (builder)
# --------------------------------------------------------------------------- #
class MenuListView(AdminAccessMixin, SectionMixin, ListView):
    permission_required = ("accounts.access_admin", "accounts.manage_settings")
    template_name = "dashboard/menu_list.html"
    context_object_name = "menus"
    section = "menus"
    heading = "Menus"

    def get_queryset(self):
        return services.list_menus()


class MenuCreateView(AdminAccessMixin, SectionMixin, CreateView):
    permission_required = ("accounts.access_admin", "accounts.manage_settings")
    model = Menu
    form_class = MenuForm
    template_name = "dashboard/menu_form.html"
    section = "menus"
    heading = "New menu"

    def get_success_url(self):
        messages.success(self.request, "Menu created.")
        return reverse_lazy("dashboard:menu_manage", args=[self.object.pk])


class MenuDeleteView(AdminAccessMixin, View):
    permission_required = ("accounts.access_admin", "accounts.manage_settings")
    http_method_names = ["post"]

    def post(self, request, pk: int):
        services.delete_menu(pk)
        messages.success(request, "Menu deleted.")
        return redirect("dashboard:menu_list")


class MenuManageView(AdminAccessMixin, SectionMixin, TemplateView):
    permission_required = ("accounts.access_admin", "accounts.manage_settings")
    template_name = "dashboard/menu_manage.html"
    section = "menus"
    heading = "Edit menu"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        menu = services.get_menu(self.kwargs["pk"])
        ctx["menu"] = menu
        ctx["items"] = services.menu_tree(menu)
        return ctx


class MenuItemCreateView(
    AdminAccessMixin, SectionMixin, DashboardTranslatableFormMixin, CreateView
):
    permission_required = ("accounts.access_admin", "accounts.manage_settings")
    model = MenuItem
    form_class = MenuItemForm
    template_name = "dashboard/menu_item_form.html"
    section = "menus"
    heading = "Add menu item"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["menu"] = services.get_menu(self.kwargs["pk"])
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["menu"] = services.get_menu(self.kwargs["pk"])
        return ctx

    def form_valid(self, form):
        services.prepare_new_menu_item(form.instance, services.get_menu(self.kwargs["pk"]))
        messages.success(self.request, "Item added.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("dashboard:menu_manage", args=[self.kwargs["pk"]])


class MenuItemUpdateView(
    AdminAccessMixin, SectionMixin, DashboardTranslatableFormMixin, UpdateView
):
    permission_required = ("accounts.access_admin", "accounts.manage_settings")
    model = MenuItem
    form_class = MenuItemForm
    template_name = "dashboard/menu_item_form.html"
    section = "menus"
    heading = "Edit menu item"

    def get_object(self, queryset=None):
        item = services.get_menu_item(services.get_menu(self.kwargs["pk"]), self.kwargs["item_pk"])
        # Mirror parler's own get_object: edit the translation for the ?language= tab
        # (our get_language clamps unknown codes), not whatever language is active.
        item.set_current_language(self.get_language(), initialize=True)
        return item

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["menu"] = services.get_menu(self.kwargs["pk"])
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["menu"] = services.get_menu(self.kwargs["pk"])
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Item updated.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("dashboard:menu_manage", args=[self.kwargs["pk"]])


class MenuItemDeleteView(AdminAccessMixin, View):
    permission_required = ("accounts.access_admin", "accounts.manage_settings")
    http_method_names = ["post"]

    def post(self, request, pk: int, item_pk: int):
        services.delete_menu_item(services.get_menu(pk), item_pk)
        messages.success(request, "Item removed.")
        return redirect("dashboard:menu_manage", pk=pk)


class MenuItemMoveView(AdminAccessMixin, View):
    permission_required = ("accounts.access_admin", "accounts.manage_settings")
    http_method_names = ["post"]

    def post(self, request, pk: int, item_pk: int, direction: str):
        services.move_menu_item(services.get_menu(pk), item_pk, direction)
        return redirect("dashboard:menu_manage", pk=pk)


class MenuItemReorderView(AdminAccessMixin, View):
    """JSON endpoint for the drag-drop builder — persists a new sibling order.

    Progressive enhancement only: the keyboard ↑/↓ move endpoints remain the
    no-JS path. Expects ``{"order": [id, ...]}``; the service renumbers those
    items' positions (ids outside this menu are ignored by the repository).
    """

    permission_required = ("accounts.access_admin", "accounts.manage_settings")
    http_method_names = ["post"]

    def post(self, request, pk: int):
        try:
            payload = json.loads(request.body or b"{}")
            order = [int(i) for i in payload.get("order", [])]
        except (ValueError, TypeError):
            return JsonResponse({"ok": False, "error": "invalid payload"}, status=400)
        services.reorder_menu_items(services.get_menu(pk), order)
        return JsonResponse({"ok": True})
