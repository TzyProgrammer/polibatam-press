"""Aturan keranjang belanja campuran (FR-08): buku cetak, ebook, dan audiobook dalam satu keranjang."""

from django.db import transaction

from apps.catalog.ketersediaan import ketersediaan
from apps.catalog.models import Produk
from apps.drm.models import HakAkses

from .models import ItemKeranjang, Keranjang

BATAS_JUMLAH = 99


class GagalKeranjang(Exception):
    """Pesan error yang aman ditampilkan ke pembeli (HTTP 400)."""


class ItemTidakDitemukan(Exception):
    """Item tidak ada atau bukan milik keranjang pembeli (HTTP 404)."""


def keranjang_milik(pembeli, kunci=False):
    keranjang, _ = Keranjang.objects.get_or_create(pembeli=pembeli)
    if kunci:
        # Mengunci baris keranjang agar dua permintaan bersamaan tidak saling menimpa.
        keranjang = Keranjang.objects.select_for_update().get(pk=keranjang.pk)
    return keranjang


def sudah_dimiliki(pembeli, produk):
    return produk.is_digital and HakAkses.objects.filter(pembeli=pembeli, produk=produk).exists()


def _periksa_jumlah(produk, jumlah):
    if produk.is_digital:
        if jumlah != 1:
            raise GagalKeranjang("Produk digital hanya bisa dibeli satu kali (jumlah 1).")
    elif jumlah > produk.stok:
        raise GagalKeranjang(f"Stok tidak mencukupi. Tersisa {produk.stok}.")
    if jumlah > BATAS_JUMLAH:
        raise GagalKeranjang(f"Jumlah maksimal {BATAS_JUMLAH} per produk.")


@transaction.atomic
def tambah_item(pembeli, produk_id, jumlah=1):
    produk = Produk.objects.select_related("buku", "paket_audio").filter(pk=produk_id).first()
    if produk is None:
        raise GagalKeranjang("Produk tidak ditemukan.")
    tersedia, keterangan = ketersediaan(produk)
    if not tersedia:
        raise GagalKeranjang(f"Produk tidak tersedia: {keterangan.lower()}.")
    if sudah_dimiliki(pembeli, produk):
        raise GagalKeranjang("Anda sudah memiliki produk ini. Buka di Koleksi.")
    keranjang = keranjang_milik(pembeli, kunci=True)
    item = keranjang.item.filter(produk=produk).first()
    if item is not None:
        if produk.is_digital:
            raise GagalKeranjang("Produk ini sudah ada di keranjang.")
        jumlah += item.jumlah  # buku cetak: jumlah ditambahkan ke item yang sudah ada
    _periksa_jumlah(produk, jumlah)
    if item is None:
        ItemKeranjang.objects.create(keranjang=keranjang, produk=produk, jumlah=jumlah)
    else:
        item.jumlah = jumlah
        item.save(update_fields=["jumlah"])
    return keranjang


def _item_milik(keranjang, item_id):
    item = keranjang.item.select_related("produk__buku").filter(pk=item_id).first()
    if item is None:
        raise ItemTidakDitemukan
    return item


@transaction.atomic
def ubah_jumlah(pembeli, item_id, jumlah):
    keranjang = keranjang_milik(pembeli, kunci=True)
    item = _item_milik(keranjang, item_id)
    if item.produk.is_digital and jumlah != 1:
        raise GagalKeranjang("Jumlah produk digital selalu 1.")
    _periksa_jumlah(item.produk, jumlah)
    item.jumlah = jumlah
    item.save(update_fields=["jumlah"])
    return keranjang


@transaction.atomic
def hapus_item(pembeli, item_id):
    keranjang = keranjang_milik(pembeli, kunci=True)
    _item_milik(keranjang, item_id).delete()
    return keranjang


def ringkasan(keranjang):
    """Isi keranjang beserta status setiap item saat ini (stok bisa berubah setelah item ditambahkan)."""
    item_list = list(
        keranjang.item.select_related("produk__buku__kategori", "produk__paket_audio").order_by("ditambahkan", "pk")
    )
    dimiliki = set(
        HakAkses.objects.filter(
            pembeli=keranjang.pembeli, produk_id__in=[i.produk_id for i in item_list if i.produk.is_digital]
        ).values_list("produk_id", flat=True)
    )
    baris = []
    for item in item_list:
        produk = item.produk
        tersedia, keterangan = ketersediaan(produk)
        if tersedia and produk.id in dimiliki:
            tersedia, keterangan = False, "Sudah dimiliki"
        elif tersedia and not produk.is_digital and item.jumlah > produk.stok:
            tersedia, keterangan = False, f"Stok tersisa {produk.stok}"
        baris.append({"item": item, "tersedia": tersedia, "keterangan": keterangan})
    return {
        "baris": baris,
        "jumlah_item": sum(b["item"].jumlah for b in baris),
        "total": sum(b["item"].subtotal for b in baris if b["tersedia"]),
        "perlu_pengiriman": any(not b["item"].produk.is_digital for b in baris),
        "semua_tersedia": all(b["tersedia"] for b in baris),
    }
