from django.urls import path

from .views import BacaNotifikasiView, BacaSemuaNotifikasiView, DaftarNotifikasiView

urlpatterns = [
    path("", DaftarNotifikasiView.as_view(), name="notifikasi"),
    path("baca-semua/", BacaSemuaNotifikasiView.as_view(), name="notifikasi-baca-semua"),
    path("<int:notifikasi_id>/baca/", BacaNotifikasiView.as_view(), name="notifikasi-baca"),
]
