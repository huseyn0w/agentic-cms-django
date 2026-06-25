from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.DashboardHomeView.as_view(), name="home"),
    # Posts
    path("posts/", views.PostListView.as_view(), name="post_list"),
    path("posts/bulk/", views.PostBulkActionView.as_view(), name="post_bulk_action"),
    path("posts/trash/", views.PostTrashListView.as_view(), name="post_trash"),
    path("posts/new/", views.PostCreateView.as_view(), name="post_create"),
    path("posts/<int:pk>/edit/", views.PostUpdateView.as_view(), name="post_edit"),
    path("posts/<int:pk>/delete/", views.PostDeleteView.as_view(), name="post_delete"),
    path("posts/<int:pk>/restore/", views.PostRestoreView.as_view(), name="post_restore"),
    path("posts/<int:pk>/destroy/", views.PostDestroyView.as_view(), name="post_destroy"),
    path(
        "posts/<int:pk>/revisions/",
        views.PostRevisionListView.as_view(),
        name="post_revisions",
    ),
    path(
        "posts/<int:pk>/revisions/<int:revision_pk>/restore/",
        views.PostRevisionRestoreView.as_view(),
        name="post_revision_restore",
    ),
    # Pages
    path("pages/", views.PageListView.as_view(), name="page_list"),
    path("pages/trash/", views.PageTrashListView.as_view(), name="page_trash"),
    path("pages/new/", views.PageCreateView.as_view(), name="page_create"),
    path("pages/<int:pk>/edit/", views.PageUpdateView.as_view(), name="page_edit"),
    path("pages/<int:pk>/delete/", views.PageDeleteView.as_view(), name="page_delete"),
    path("pages/<int:pk>/restore/", views.PageRestoreView.as_view(), name="page_restore"),
    path("pages/<int:pk>/destroy/", views.PageDestroyView.as_view(), name="page_destroy"),
    path(
        "pages/<int:pk>/revisions/",
        views.PageRevisionListView.as_view(),
        name="page_revisions",
    ),
    path(
        "pages/<int:pk>/revisions/<int:revision_pk>/restore/",
        views.PageRevisionRestoreView.as_view(),
        name="page_revision_restore",
    ),
    # Services (GEO)
    path("services/", views.ServiceListView.as_view(), name="service_list"),
    path("services/new/", views.ServiceCreateView.as_view(), name="service_create"),
    path("services/<int:pk>/edit/", views.ServiceUpdateView.as_view(), name="service_edit"),
    path("services/<int:pk>/delete/", views.ServiceDeleteView.as_view(), name="service_delete"),
    # Categories
    path("categories/", views.CategoryListView.as_view(), name="category_list"),
    path("categories/new/", views.CategoryCreateView.as_view(), name="category_create"),
    path("categories/<int:pk>/edit/", views.CategoryUpdateView.as_view(), name="category_edit"),
    path("categories/<int:pk>/delete/", views.CategoryDeleteView.as_view(), name="category_delete"),
    # Tags
    path("tags/", views.TagListView.as_view(), name="tag_list"),
    path("tags/new/", views.TagCreateView.as_view(), name="tag_create"),
    path("tags/<int:pk>/edit/", views.TagUpdateView.as_view(), name="tag_edit"),
    path("tags/<int:pk>/delete/", views.TagDeleteView.as_view(), name="tag_delete"),
    # Users
    path("users/", views.UserListView.as_view(), name="user_list"),
    path("users/<int:pk>/edit/", views.UserUpdateView.as_view(), name="user_edit"),
    # Appearance / themes
    path("appearance/", views.ThemeListView.as_view(), name="themes"),
    path(
        "appearance/<slug:slug>/activate/", views.ThemeActivateView.as_view(), name="theme_activate"
    ),
    # Plugins
    path("plugins/", views.PluginListView.as_view(), name="plugins"),
    path("plugins/<slug:slug>/toggle/", views.PluginToggleView.as_view(), name="plugin_toggle"),
    # Menus (builder)
    path("menus/", views.MenuListView.as_view(), name="menu_list"),
    path("menus/new/", views.MenuCreateView.as_view(), name="menu_create"),
    path("menus/<int:pk>/", views.MenuManageView.as_view(), name="menu_manage"),
    path("menus/<int:pk>/delete/", views.MenuDeleteView.as_view(), name="menu_delete"),
    path("menus/<int:pk>/items/new/", views.MenuItemCreateView.as_view(), name="menu_item_create"),
    path(
        "menus/<int:pk>/items/<int:item_pk>/edit/",
        views.MenuItemUpdateView.as_view(),
        name="menu_item_edit",
    ),
    path(
        "menus/<int:pk>/items/<int:item_pk>/delete/",
        views.MenuItemDeleteView.as_view(),
        name="menu_item_delete",
    ),
    path(
        "menus/<int:pk>/items/<int:item_pk>/move/<str:direction>/",
        views.MenuItemMoveView.as_view(),
        name="menu_item_move",
    ),
    # Comments (moderation)
    path("comments/", views.CommentListView.as_view(), name="comment_list"),
    path(
        "comments/<int:pk>/<str:action>/",
        views.CommentModerateView.as_view(),
        name="comment_moderate",
    ),
    # Settings
    path("settings/", views.SettingsView.as_view(), name="settings"),
    path("settings/seo/", views.SeoSettingsView.as_view(), name="seo_settings"),
]
