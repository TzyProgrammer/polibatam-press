from django.apps import AppConfig


class OrdersConfig(AppConfig):
    name = "apps.orders"
    verbose_name = "Pesanan"

    def ready(self):
        from . import checks  # noqa: F401  (mendaftarkan pemeriksaan pengaturan Midtrans dan checkout)
