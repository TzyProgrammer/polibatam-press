from django.contrib import admin
from django.urls import include, path

from apps.drm.views import uji_pemutar
from core.views import health

admin.site.site_header = "Admin Marketplace Polibatam Press"
admin.site.site_title = "Admin Marketplace Polibatam Press"
admin.site.index_title = "Admin Marketplace Polibatam Press"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/drm/", include("apps.drm.urls")),
    # Halaman uji pemutar audiobook; mengembalikan 404 bila DEBUG=False.
    path("uji-pemutar/", uji_pemutar, name="uji-pemutar"),
]
