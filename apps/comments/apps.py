from django.apps import AppConfig


class CommentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.comments"
    verbose_name = "Comments"

    def ready(self) -> None:
        # Register the comment_created observers (email notification to the author).
        from . import signals  # noqa: F401
