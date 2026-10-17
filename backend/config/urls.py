from django.contrib import admin
from django.urls import path

from core.views import health

admin.site.site_header = "Admin Marketplace Polibatam Press"
admin.site.site_title = "Admin Marketplace Polibatam Press"
admin.site.index_title = "Admin Marketplace Polibatam Press"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health),
]
