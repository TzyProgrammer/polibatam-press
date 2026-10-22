from rest_framework import generics
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notifikasi
from .serializers import NotifikasiSerializer


def jumlah_belum_dibaca(pengguna):
    return Notifikasi.objects.filter(penerima=pengguna, dibaca=False).count()


class HalamanNotifikasi(PageNumberPagination):
    page_size = 20
    invalid_page_message = "Halaman tidak ditemukan."

    def get_paginated_response(self, data):
        response = super().get_paginated_response(data)
        # Untuk angka pada ikon lonceng, tanpa permintaan terpisah.
        response.data["belum_dibaca"] = jumlah_belum_dibaca(self.request.user)
        return response


class DaftarNotifikasiView(generics.ListAPIView):
    """GET /api/notifikasi/?belum_dibaca=1 — notifikasi milik pengguna, terbaru lebih dulu."""

    serializer_class = NotifikasiSerializer
    pagination_class = HalamanNotifikasi

    def get_queryset(self):
        qs = Notifikasi.objects.filter(penerima=self.request.user)
        if self.request.query_params.get("belum_dibaca") in ("1", "true"):
            qs = qs.filter(dibaca=False)
        return qs.order_by("-dibuat", "-id")


class BacaNotifikasiView(APIView):
    """POST /api/notifikasi/<id>/baca/ — tandai satu notifikasi milik pengguna sudah dibaca."""

    def post(self, request, notifikasi_id):
        notifikasi = Notifikasi.objects.filter(pk=notifikasi_id, penerima=request.user).first()
        if notifikasi is None:
            raise NotFound("Notifikasi tidak ditemukan.")
        if not notifikasi.dibaca:
            notifikasi.dibaca = True
            notifikasi.save(update_fields=["dibaca"])
        return Response(NotifikasiSerializer(notifikasi).data)


class BacaSemuaNotifikasiView(APIView):
    """POST /api/notifikasi/baca-semua/ — tandai semua notifikasi pengguna sudah dibaca."""

    def post(self, request):
        ditandai = Notifikasi.objects.filter(penerima=request.user, dibaca=False).update(dibaca=True)
        return Response({"ditandai": ditandai, "belum_dibaca": 0})
