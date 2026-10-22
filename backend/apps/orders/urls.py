from django.urls import path

from .views import (
    CekStatusPesananView,
    CheckoutView,
    DaftarPesananView,
    DetailPesananView,
    ItemKeranjangView,
    KeranjangView,
    NotifikasiMidtransView,
    TambahItemView,
)

urlpatterns = [
    path("keranjang/", KeranjangView.as_view(), name="keranjang"),
    path("keranjang/item/", TambahItemView.as_view(), name="keranjang-item"),
    path("keranjang/item/<int:item_id>/", ItemKeranjangView.as_view(), name="keranjang-item-detail"),
    path("pesanan/", DaftarPesananView.as_view(), name="pesanan"),
    path("pesanan/checkout/", CheckoutView.as_view(), name="checkout"),
    path("pesanan/<str:nomor>/", DetailPesananView.as_view(), name="pesanan-detail"),
    path("pesanan/<str:nomor>/cek-status/", CekStatusPesananView.as_view(), name="pesanan-cek-status"),
    path("pembayaran/midtrans/notifikasi/", NotifikasiMidtransView.as_view(), name="midtrans-notifikasi"),
]
