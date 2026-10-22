from django.urls import path

from .views import DaftarBukuView, DaftarKategoriView, DetailBukuView

urlpatterns = [
    path("buku/", DaftarBukuView.as_view(), name="katalog-buku"),
    path("buku/<slug:slug>/", DetailBukuView.as_view(), name="katalog-buku-detail"),
    path("kategori/", DaftarKategoriView.as_view(), name="katalog-kategori"),
]
