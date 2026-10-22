from django.db import transaction
from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.notifications import layanan as notifikasi

from .models import PengajuanISBN
from .serializers import PengajuanBaruSerializer, PengajuanDetailSerializer, PengajuanSerializer


class HalamanPengajuan(PageNumberPagination):
    page_size = 10
    invalid_page_message = "Halaman tidak ditemukan."


class PengajuanISBNView(generics.ListCreateAPIView):
    """GET /api/isbn/pengajuan/ — pengajuan milik pemohon; POST — ajukan naskah (FR-14).

    POST memakai multipart/form-data karena berisi berkas naskah.
    """

    pagination_class = HalamanPengajuan
    parser_classes = [MultiPartParser, FormParser]
    throttle_scope = "pengajuan_isbn"

    def get_throttles(self):
        # Hanya pengajuan baru (unggah berkas) yang dibatasi; melihat daftar tidak.
        return super().get_throttles() if self.request.method == "POST" else []

    def get_queryset(self):
        return PengajuanISBN.objects.filter(pemohon=self.request.user).order_by("-diajukan", "-pk")

    def get_serializer_class(self):
        return PengajuanBaruSerializer if self.request.method == "POST" else PengajuanSerializer

    def create(self, request, *args, **kwargs):
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        with transaction.atomic():
            pengajuan = data.save(pemohon=request.user)
            notifikasi.isbn_diajukan(pengajuan)
        return Response(PengajuanDetailSerializer(pengajuan).data, status=status.HTTP_201_CREATED)


class DetailPengajuanISBNView(generics.RetrieveAPIView):
    """GET /api/isbn/pengajuan/<id>/ — status pengajuan milik pemohon (FR-15)."""

    serializer_class = PengajuanDetailSerializer

    def get_object(self):
        pengajuan = PengajuanISBN.objects.filter(pk=self.kwargs["pk"], pemohon=self.request.user).first()
        if pengajuan is None:
            raise NotFound("Pengajuan tidak ditemukan.")
        return pengajuan
