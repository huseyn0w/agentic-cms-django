from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("authors/<int:pk>/", views.AuthorDetailView.as_view(), name="author_detail"),
    path("account/", views.ProfileUpdateView.as_view(), name="profile"),
]
