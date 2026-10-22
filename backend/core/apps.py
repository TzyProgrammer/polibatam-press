import logging

from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"

    def ready(self):
        from .log import SaringTokenSesi

        # Access log runserver (django.server) dan peringatan 4xx/5xx (django.request) memuat path URL,
        # termasuk token sesi streaming. Nginx menyamarkannya sendiri (nginx/default.conf).
        penyaring = SaringTokenSesi()
        for nama in ("django.server", "django.request"):
            logging.getLogger(nama).addFilter(penyaring)
