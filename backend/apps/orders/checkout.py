"""Checkout (FR-09, FR-10): seluruh isi keranjang menjadi satu pesanan dengan transaksi Snap Midtrans.

Semua langkah berada dalam satu transaksi basis data. Bila stok tidak cukup atau Snap gagal dibuat,
tidak ada yang berubah: pesanan tidak tersimpan, stok utuh, dan keranjang tetap berisi.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.catalog.models import Produk

from . import midtrans
from .keranjang import keranjang_milik, ringkasan
from .models import ItemPesanan, Pesanan

logger = logging.getLogger(__name__)

# Delivery hanya untuk wilayah Kota Batam (12 kecamatan) dengan ongkir tetap.
KECAMATAN_KOTA_BATAM = (
    "Batam Kota",
    "Batu Aji",
    "Batu Ampar",
    "Belakang Padang",
    "Bengkong",
    "Bulang",
    "Galang",
    "Lubuk Baja",
    "Nongsa",
    "Sagulung",
    "Sei Beduk",
    "Sekupang",
)

# Nama item di Snap maksimal 50 karakter.
PANJANG_NAMA_ITEM = 50
LABEL_SINGKAT = {"cetak": "Cetak", "ebook": "Ebook", "audiobook": "Audiobook"}


class GagalCheckout(Exception):
    """Pesan error yang aman ditampilkan ke pembeli (HTTP 400)."""


class PembayaranTidakTersedia(Exception):
    """Transaksi Snap gagal dibuat; checkout dibatalkan seluruhnya."""

    def __init__(self, belum_dikonfigurasi=False):
        super().__init__()
        self.belum_dikonfigurasi = belum_dikonfigurasi


def ongkir(metode):
    return settings.ONGKIR_KOTA_BATAM if metode == Pesanan.MetodePengiriman.DELIVERY else 0


def opsi_pengiriman():
    """Pilihan pengiriman untuk layar checkout (dipakai GET /api/pesanan/checkout/)."""
    metode = Pesanan.MetodePengiriman
    return {
        "delivery": {
            "label": metode.DELIVERY.label,
            "ongkir": ongkir(metode.DELIVERY),
            "kecamatan": list(KECAMATAN_KOTA_BATAM),
        },
        "takeaway": {
            "label": metode.TAKEAWAY.label,
            "ongkir": 0,
            "lokasi": settings.LOKASI_TAKEAWAY,
        },
    }


def _item_tidak_tersedia(isi):
    daftar = [
        f"{b['item'].produk.buku.judul} ({b['item'].produk.get_format_display()}): {b['keterangan']}"
        for b in isi["baris"]
        if not b["tersedia"]
    ]
    return "Ada produk yang tidak bisa dibeli: " + "; ".join(daftar) + ". Perbarui keranjang Anda."


@transaction.atomic
def buat_pesanan(pembeli, pengiriman):
    """Membuat pesanan dari keranjang pembeli lalu transaksi Snap.

    `pengiriman` adalah hasil CheckoutSerializer: metode_pengiriman ("" bila tidak dipilih),
    nama_penerima, no_telepon_penerima, alamat_pengiriman.
    """
    keranjang = keranjang_milik(pembeli, kunci=True)
    isi = ringkasan(keranjang)
    if not isi["baris"]:
        raise GagalCheckout("Keranjang kosong.")
    if not isi["semua_tersedia"]:
        raise GagalCheckout(_item_tidak_tersedia(isi))

    if isi["perlu_pengiriman"]:
        metode = pengiriman.get("metode_pengiriman")
        if not metode:
            raise GagalCheckout("Pilih metode pengiriman untuk buku cetak: delivery (Kota Batam) atau takeaway.")
    else:
        # Pesanan yang semuanya digital tidak memerlukan pengiriman; isian pengiriman diabaikan.
        metode = Pesanan.MetodePengiriman.TANPA
    dikirim = metode != Pesanan.MetodePengiriman.TANPA

    # Detik dibulatkan agar sama persis dengan start_time yang dikirim ke Snap.
    mulai = timezone.now().replace(microsecond=0)
    biaya_kirim = ongkir(metode)
    pesanan = Pesanan.objects.create(
        pembeli=pembeli,
        metode_pengiriman=metode,
        status_pengiriman=(
            Pesanan.StatusPengiriman.MENUNGGU if dikirim else Pesanan.StatusPengiriman.TIDAK_ADA
        ),
        nama_penerima=pengiriman.get("nama_penerima", "") if dikirim else "",
        no_telepon_penerima=pengiriman.get("no_telepon_penerima", "") if dikirim else "",
        alamat_pengiriman=pengiriman.get("alamat_pengiriman", "") if dikirim else "",
        subtotal=isi["total"],
        ongkir=biaya_kirim,
        total=isi["total"] + biaya_kirim,
        batas_bayar=mulai + timedelta(minutes=settings.BATAS_BAYAR_MENIT),
    )

    item_pesanan = []
    for baris in isi["baris"]:
        item = baris["item"]
        produk = item.produk
        if not produk.is_digital:
            # Stok dipesan sekarang dengan UPDATE bersyarat, jadi dua checkout bersamaan tidak bisa
            # sama-sama mengambil stok terakhir. Stok kembali bila pesanan tidak dibayar.
            dipesan = Produk.objects.filter(pk=produk.pk, stok__gte=item.jumlah).update(
                stok=F("stok") - item.jumlah
            )
            if not dipesan:
                raise GagalCheckout(f"Stok {produk.buku.judul} tidak mencukupi. Perbarui keranjang Anda.")
        item_pesanan.append(
            ItemPesanan.objects.create(
                pesanan=pesanan,
                produk=produk,
                judul=produk.buku.judul,
                format=produk.format,
                harga_satuan=produk.harga,
                jumlah=item.jumlah,
            )
        )
    keranjang.item.all().delete()

    try:
        snap = midtrans.buat_transaksi_snap(payload_snap(pesanan, item_pesanan, mulai))
    except midtrans.BelumDikonfigurasi as exc:
        logger.error("Checkout %s dibatalkan: %s", pesanan.nomor, exc)
        raise PembayaranTidakTersedia(belum_dikonfigurasi=True) from exc
    except midtrans.GagalMidtrans as exc:
        logger.error("Checkout %s dibatalkan: %s", pesanan.nomor, exc)
        raise PembayaranTidakTersedia from exc
    pesanan.snap_token = snap["token"]
    pesanan.snap_redirect_url = snap["redirect_url"]
    pesanan.save(update_fields=["snap_token", "snap_redirect_url", "diperbarui"])
    logger.info("Pesanan %s dibuat (total %s, batas bayar %s).", pesanan.nomor, pesanan.total, pesanan.batas_bayar)
    return pesanan


def nama_item(item):
    """Nama item untuk Snap, maksimal 50 karakter, misalnya "Keamanan Data Modern (Ebook)"."""
    label = f" ({LABEL_SINGKAT.get(item.format, item.format)})"
    judul = " ".join(item.judul.split()).replace("|", "/")
    ruang = PANJANG_NAMA_ITEM - len(label)
    if len(judul) > ruang:
        judul = judul[: ruang - 3].rstrip() + "..."
    return judul + label


def payload_snap(pesanan, item_pesanan, mulai):
    """Isi permintaan Snap API. Jumlah harga × kuantitas semua item harus sama dengan gross_amount."""
    rincian = [
        {"id": str(item.produk_id), "price": item.harga_satuan, "quantity": item.jumlah, "name": nama_item(item)}
        for item in item_pesanan
    ]
    if pesanan.ongkir:
        rincian.append({"id": "ONGKIR", "price": pesanan.ongkir, "quantity": 1, "name": "Ongkos kirim Kota Batam"})
    pembeli = pesanan.pembeli
    pelanggan = {
        "first_name": (pesanan.nama_penerima or pembeli.nama_lengkap or pembeli.email)[:255],
        "email": pembeli.email,
    }
    telepon = pesanan.no_telepon_penerima or pembeli.no_telepon
    if telepon:
        pelanggan["phone"] = telepon
    return {
        "transaction_details": {"order_id": pesanan.nomor, "gross_amount": pesanan.total},
        "item_details": rincian,
        "customer_details": pelanggan,
        "enabled_payments": list(settings.MIDTRANS_ENABLED_PAYMENTS),
        # Kedaluwarsa dihitung sejak checkout (bukan sejak pembeli memilih metode bayar) agar sama
        # dengan batas_bayar; halaman Snap juga tidak bisa dipakai setelah itu.
        "expiry": {
            "start_time": timezone.localtime(mulai).strftime("%Y-%m-%d %H:%M:%S %z"),
            "unit": "minute",
            "duration": settings.BATAS_BAYAR_MENIT,
        },
        "page_expiry": {"duration": settings.BATAS_BAYAR_MENIT, "unit": "minute"},
    }
