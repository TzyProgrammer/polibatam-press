from django.contrib import admin
from django.urls import include, path

from apps.drm.views import KoleksiView, uji_pemutar
from core.views import health

from . import sandi_admin

urlpatterns = [
    # Lupa kata sandi Django Admin; nama URL mengikuti bawaan Django agar tautannya tampil di halaman masuk admin.
    # Harus di atas admin.site.urls (yang menolak alamat lain di bawah /admin/).
    path("admin/lupa-sandi/", sandi_admin.LupaSandiAdminView.as_view(), name="admin_password_reset"),
    path("admin/lupa-sandi/terkirim/", sandi_admin.LupaSandiAdminTerkirimView.as_view(), name="password_reset_done"),
    path(
        "admin/atur-ulang-sandi/<uidb64>/<token>/",
        sandi_admin.AturUlangSandiAdminView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "admin/atur-ulang-sandi/selesai/",
        sandi_admin.AturUlangSandiAdminSelesaiView.as_view(),
        name="password_reset_complete",
    ),
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
