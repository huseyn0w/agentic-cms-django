from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = "api"

router = DefaultRouter()
router.register("posts", views.PostViewSet, basename="post")
router.register("pages", views.PageViewSet, basename="page")
router.register("services", views.ServiceViewSet, basename="service")
router.register("categories", views.CategoryViewSet, basename="category")
router.register("tags", views.TagViewSet, basename="tag")

urlpatterns = [
    path("v1/", include((router.urls, "v1"))),
]
