from django.urls import reverse
from rest_framework import serializers

from apps.catalog.models import Produk
from apps.catalog.serializers import url_sampul

from .models import HakAkses


def status_konten(hak):
    """(status, keterangan) konten digital milik pembeli untuk ditampilkan di Koleksi."""
    if not hak.aktif:
        return "dicabut", "Akses dinonaktifkan admin"
    if hak.produk.format == Produk.Format.EBOOK:
        salinan = getattr(hak, "salinan_ebook", None)
        if salinan is None:
            return "menunggu", "Salinan ber-watermark akan disiapkan saat dibuka"
        return salinan.status, salinan.get_status_display()
    paket = getattr(hak.produk, "paket_audio", None)
    if paket is None:
        return "menunggu", "Audiobook sedang disiapkan"
    return paket.status, paket.get_status_display()


class KoleksiSerializer(serializers.ModelSerializer):
    """Satu produk digital di Koleksi pembeli (FR-13).

    `url_akses`: ebook dibuka dengan GET (salinan ber-watermark), audiobook dengan POST (sesi streaming).
    """

    produk_id = serializers.IntegerField()
    format = serializers.CharField(source="produk.format")
    format_label = serializers.CharField(source="produk.get_format_display")
    buku = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    keterangan = serializers.SerializerMethodField()
    url_akses = serializers.SerializerMethodField()
    nomor_pesanan = serializers.CharField(source="item_pesanan.pesanan.nomor")
    diperoleh = serializers.DateTimeField(source="diberikan")

    class Meta:
        model = HakAkses
        fields = [
            "produk_id",
            "format",
            "format_label",
            "buku",
            "aktif",
            "status",
            "keterangan",
            "url_akses",
            "nomor_pesanan",
            "diperoleh",
        ]

    def get_buku(self, hak):
        buku = hak.produk.buku
        return {"judul": buku.judul, "slug": buku.slug, "penulis": buku.penulis, "sampul": url_sampul(buku)}

    def get_status(self, hak):
        return status_konten(hak)[0]

    def get_keterangan(self, hak):
        return status_konten(hak)[1]

    def get_url_akses(self, hak):
        if hak.produk.format == Produk.Format.EBOOK:
            return reverse("drm-ebook", args=[hak.produk_id])
        return reverse("drm-sesi-baru", args=[hak.produk_id])
