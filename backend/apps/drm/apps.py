from django.apps import AppConfig


class DrmConfig(AppConfig):
    name = "apps.drm"

    def ready(self):
        from . import checks, signals  # noqa: F401  (mendaftarkan pemeriksaan .env dan sinyal)
