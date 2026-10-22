"""Alat bantu tes data katalog (dipakai tes katalog dan keranjang)."""

from datetime import timedelta
from unittest import mock

from django.utils import timezone

from core.testing import berkas_uji

from .models import Buku, Produk


def buat_buku(judul, penulis="Penulis", kategori=None, aktif=True, umur_hari=0, **lain):
    buku = Buku.objects.create(judul=judul, penulis=penulis, kategori=kategori, aktif=aktif, **lain)
    # Waktu dibuat diatur agar urutan "terbaru" bisa diuji secara pasti.
    Buku.objects.filter(pk=buku.pk).update(dibuat=timezone.now() - timedelta(days=umur_hari))
    buku.refresh_from_db()
    return buku


def buat_produk(buku, format_produk, harga, **lain):
    """Produk dengan berkas contoh untuk format digital; task pengemasan audiobook tidak dijalankan."""
    from apps.drm.tasks import kemas_audiobook

    if format_produk == Produk.Format.EBOOK:
        lain.setdefault("berkas", berkas_uji("buku.pdf"))
    if format_produk == Produk.Format.AUDIOBOOK:
        lain.setdefault("berkas", berkas_uji("audio.mp3"))
    with mock.patch.object(kemas_audiobook, "delay"):
        return Produk.objects.create(buku=buku, format=format_produk, harga=harga, **lain)
