from django.urls import path

from . import views
from .feeds import CategoryPostsFeed

app_name = "content"

urlpatterns = [
    path("blog/", views.PostListView.as_view(), name="post_list"),
    path("blog/category/<slug:slug>/", views.CategoryPostListView.as_view(), name="category"),
    path(
        "blog/category/<slug:slug>/rss.xml",
        CategoryPostsFeed(),
        name="category_rss",
    ),
    path("blog/tag/<slug:slug>/", views.TagPostListView.as_view(), name="tag"),
    path("blog/<slug:slug>/", views.PostDetailView.as_view(), name="post_detail"),
    path("blog/<slug:slug>/like/", views.PostLikeView.as_view(), name="post_like"),
    path("services/", views.ServiceListView.as_view(), name="service_list"),
    path("services/<slug:slug>/", views.ServiceDetailView.as_view(), name="service_detail"),
    path("pages/<slug:slug>/", views.PageDetailView.as_view(), name="page_detail"),
]
