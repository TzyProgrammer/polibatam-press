from django.contrib import admin
from django.urls import include, path

from apps.drm.views import KoleksiView, uji_pemutar
from core.views import health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/drm/", include("apps.drm.urls")),
    path("api/katalog/", include("apps.catalog.urls")),
    path("api/koleksi/", KoleksiView.as_view(), name="koleksi"),
    path("api/isbn/", include("apps.isbn.urls")),
    path("api/notifikasi/", include("apps.notifications.urls")),
    # Keranjang, pesanan, dan notifikasi pembayaran Midtrans
    path("api/", include("apps.orders.urls")),
    # Halaman uji pemutar audiobook; mengembalikan 404 bila DEBUG=False.
    path("uji-pemutar/", uji_pemutar, name="uji-pemutar"),
]
