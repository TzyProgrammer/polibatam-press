"""Apakah sebuah produk bisa dibeli saat ini (dipakai katalog, keranjang, dan checkout)."""

from .models import Produk


def ketersediaan(produk):
    """Mengembalikan (tersedia, keterangan). Keterangan kosong bila tersedia.

    Untuk audiobook, akses `produk.paket_audio` sebaiknya sudah di-select_related agar tidak
    menambah kueri per produk.
    """
    from apps.drm.models import PaketAudio  # impor di sini: app drm bergantung pada catalog

    if not produk.aktif or not produk.buku.aktif:
        return False, "Tidak dijual"
    if produk.format == Produk.Format.CETAK:
        return (True, "") if produk.stok > 0 else (False, "Stok habis")
    if not produk.berkas:
        return False, "Belum tersedia"
    if produk.format == Produk.Format.AUDIOBOOK:
        paket = getattr(produk, "paket_audio", None)
        if paket is None or paket.status != PaketAudio.Status.SIAP:
            return False, "Sedang disiapkan"
    return True, ""
