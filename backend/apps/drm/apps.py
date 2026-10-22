from django.apps import AppConfig


class DrmConfig(AppConfig):
    name = "apps.drm"

    def ready(self):
        from . import signals  # noqa: F401  (mendaftarkan sinyal pengemasan audiobook)
