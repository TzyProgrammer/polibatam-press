from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import keranjang as layanan
from .serializers import TambahItemSerializer, UbahJumlahSerializer, data_keranjang


def respons_keranjang(keranjang, kode=status.HTTP_200_OK):
    return Response(data_keranjang(layanan.ringkasan(keranjang)), status=kode)


def respons_gagal(exc):
    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


def _item_tidak_ditemukan():
    return Response({"detail": "Item keranjang tidak ditemukan."}, status=status.HTTP_404_NOT_FOUND)


class KeranjangView(APIView):
    """GET /api/keranjang/ — isi keranjang pembeli (dibuat otomatis bila belum ada)."""

    def get(self, request):
        return respons_keranjang(layanan.keranjang_milik(request.user))


class TambahItemView(APIView):
    """POST /api/keranjang/item/ {produk_id, jumlah} — mengembalikan isi keranjang terbaru."""

    def post(self, request):
        data = TambahItemSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            keranjang = layanan.tambah_item(request.user, **data.validated_data)
        except layanan.GagalKeranjang as exc:
            return respons_gagal(exc)
        return respons_keranjang(keranjang, status.HTTP_201_CREATED)


class ItemKeranjangView(APIView):
    """PATCH/DELETE /api/keranjang/item/<id>/ — mengembalikan isi keranjang terbaru."""

    def patch(self, request, item_id):
        data = UbahJumlahSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            keranjang = layanan.ubah_jumlah(request.user, item_id, data.validated_data["jumlah"])
        except layanan.ItemTidakDitemukan:
            return _item_tidak_ditemukan()
        except layanan.GagalKeranjang as exc:
            return respons_gagal(exc)
        return respons_keranjang(keranjang)

    def delete(self, request, item_id):
        try:
            keranjang = layanan.hapus_item(request.user, item_id)
        except layanan.ItemTidakDitemukan:
            return _item_tidak_ditemukan()
        return respons_keranjang(keranjang)
