from django.urls import path

from .views import ItemKeranjangView, KeranjangView, TambahItemView

urlpatterns = [
    path("keranjang/", KeranjangView.as_view(), name="keranjang"),
    path("keranjang/item/", TambahItemView.as_view(), name="keranjang-item"),
    path("keranjang/item/<int:item_id>/", ItemKeranjangView.as_view(), name="keranjang-item-detail"),
]
