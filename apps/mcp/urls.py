from django.urls import path

from . import views

app_name = "mcp"

urlpatterns = [
    path("", views.MCPView.as_view(), name="endpoint"),
]
