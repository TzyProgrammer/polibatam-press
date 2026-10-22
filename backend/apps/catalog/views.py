from django.db.models import Count, Exists, IntegerField, Min, OuterRef, Prefetch, Q, Subquery, Value
from django.db.models.functions import Coalesce
from rest_framework import generics
from rest_framework.exceptions import NotFound, ParseError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny

from .models import Buku, Kategori, Produk
from .serializers import BukuDetailSerializer, BukuRingkasSerializer, KategoriSerializer

URUTAN = {
    "terbaru": ("-dibuat", "-pk"),
    "judul": ("judul", "pk"),
    "harga": ("harga_mulai", "judul"),
    "-harga": ("-harga_mulai", "judul"),
}


class HalamanKatalog(PageNumberPagination):
    page_size = 12
    page_size_query_param = "ukuran"
    max_page_size = 48
    invalid_page_message = "Halaman tidak ditemukan."


def ada_produk_aktif(**syarat):
    return Exists(Produk.objects.filter(buku=OuterRef("pk"), aktif=True, **syarat))


def buku_katalog():
    """Buku yang tampil di katalog: buku aktif yang memiliki minimal satu produk aktif."""
    produk_aktif = Produk.objects.filter(aktif=True).select_related("paket_audio").order_by("format")
    return (
        Buku.objects.filter(aktif=True)
        .filter(ada_produk_aktif())
        .select_related("kategori")
        .prefetch_related(Prefetch("produk", queryset=produk_aktif, to_attr="produk_aktif"))
        .annotate(harga_mulai=Min("produk__harga", filter=Q(produk__aktif=True)))
    )


class PublikMixin:
    # Katalog bisa dibuka tanpa login; header Authorization (bahkan yang kedaluwarsa) diabaikan.
    authentication_classes = []
    permission_classes = [AllowAny]


class DaftarBukuView(PublikMixin, generics.ListAPIView):
    """GET /api/katalog/buku/?q=&kategori=&tipe=&urutan=&page=&ukuran= (FR-05, FR-07).

    Filter jenis produk memakai ?tipe=, bukan ?format=, karena ?format= adalah parameter bawaan DRF
    untuk memilih format respons (URL_FORMAT_OVERRIDE) dan sengaja tidak diubah.
    """

    serializer_class = BukuRingkasSerializer
    pagination_class = HalamanKatalog

    def get_queryset(self):
        parameter = self.request.query_params
        qs = buku_katalog()
        for kata in parameter.get("q", "").split():
            qs = qs.filter(Q(judul__icontains=kata) | Q(penulis__icontains=kata) | Q(isbn__icontains=kata))
        kategori = parameter.get("kategori", "").strip()
        if kategori:
            qs = qs.filter(kategori__slug=kategori)
        tipe = parameter.get("tipe", "").strip()
        if tipe:
            if tipe not in Produk.Format.values:
                raise ParseError("Tipe harus salah satu dari: cetak, ebook, audiobook.")
            qs = qs.filter(ada_produk_aktif(format=tipe))
        urutan = parameter.get("urutan", "terbaru").strip() or "terbaru"
        if urutan not in URUTAN:
            raise ParseError("Urutan harus salah satu dari: terbaru, judul, harga, -harga.")
        return qs.order_by(*URUTAN[urutan])


class DetailBukuView(PublikMixin, generics.RetrieveAPIView):
    """GET /api/katalog/buku/<slug>/"""

    serializer_class = BukuDetailSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return buku_katalog()

    def get_object(self):
        buku = self.get_queryset().filter(slug=self.kwargs["slug"]).first()
        if buku is None:
            raise NotFound("Buku tidak ditemukan.")
        return buku


class DaftarKategoriView(PublikMixin, generics.ListAPIView):
    """GET /api/katalog/kategori/ beserta jumlah buku yang tampil di katalog."""

    serializer_class = KategoriSerializer

    def get_queryset(self):
        jumlah = (
            Buku.objects.filter(kategori=OuterRef("pk"), aktif=True)
            .filter(ada_produk_aktif())
            .order_by()
            .values("kategori")
            .annotate(n=Count("pk"))
            .values("n")
        )
        return Kategori.objects.annotate(
            jumlah_buku=Coalesce(Subquery(jumlah, output_field=IntegerField()), Value(0))
        ).order_by("nama")
