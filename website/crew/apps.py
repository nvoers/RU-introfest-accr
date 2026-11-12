from django.apps import AppConfig


class CrewConfig(AppConfig):
    name = "crew"

    def ready(self):
        from . import signals  # noqa: F401
