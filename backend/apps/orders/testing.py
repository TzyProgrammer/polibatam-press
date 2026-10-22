"""Alat bantu tes checkout dan pembayaran: Midtrans tiruan, tanpa permintaan ke internet."""

from unittest import mock

from django.contrib.auth import get_user_model

from apps.catalog.models import Produk
from apps.catalog.testing import buat_buku, buat_produk
from apps.drm.models import PaketAudio

from . import midtrans

# Pengaturan tetap untuk tes, agar hasilnya tidak bergantung pada isi .env pemilik repo.
PENGATURAN_UJI = {
    "MIDTRANS_SERVER_KEY": "SB-Mid-server-kunci-uji",
    "MIDTRANS_CLIENT_KEY": "SB-Mid-client-kunci-uji",
    "MIDTRANS_IS_PRODUCTION": False,
    "MIDTRANS_ENABLED_PAYMENTS": ["other_qris"],
    "BATAS_BAYAR_MENIT": 60,
    "ONGKIR_KOTA_BATAM": 15000,
    "LOKASI_TAKEAWAY": "Gedung TA Kampus Polibatam, Lantai 1 (Kantor Polibatam Store)",
}


def data_status(pesanan, transaction_status="settlement", **lain):
    """Respons Get Status API Midtrans untuk pesanan (bentuknya mengikuti dokumentasi Midtrans)."""
    data = {
        "status_code": {"settlement": "200", "capture": "200", "pending": "201"}.get(transaction_status, "202"),
        "status_message": "Success, transaction is found",
        "transaction_id": f"trx-{pesanan.nomor}",
        "order_id": pesanan.nomor,
        "gross_amount": f"{pesanan.total}.00",
        "currency": "IDR",
        "payment_type": "qris",
        "transaction_time": "2026-10-22 21:40:00",
        "transaction_status": transaction_status,
        "fraud_status": "accept",
    }
    if transaction_status == "settlement":
        data["settlement_time"] = "2026-10-22 21:45:12"
    data.update(lain)
    return data


class MidtransTiruan:
    """Pengganti Snap API dan Status API. `status[nomor]` = respons Status API (tidak ada = 404)."""

    def __init__(self):
        self.payload_snap = []
        self.status = {}
        self.panggilan_status = []
        self.gagal = None

    def buat_transaksi_snap(self, payload):
        if self.gagal:
            raise self.gagal
        self.payload_snap.append(payload)
        nomor = payload["transaction_details"]["order_id"]
        return {
            "token": f"token-{nomor}",
            "redirect_url": f"https://app.sandbox.midtrans.com/snap/v4/redirection/token-{nomor}",
        }

    def status_transaksi(self, order_id):
        self.panggilan_status.append(order_id)
        if self.gagal:
            raise self.gagal
        return self.status.get(order_id)

    def atur(self, pesanan, transaction_status="settlement", **lain):
        self.status[pesanan.nomor] = data_status(pesanan, transaction_status, **lain)


class MidtransTiruanMixin:
    """Memasang MidtransTiruan di self.midtrans. Permintaan HTTP sungguhan ke Midtrans membuat tes gagal."""

    def setUp(self):
        super().setUp()
        self.midtrans = MidtransTiruan()
        for nama in ("buat_transaksi_snap", "status_transaksi"):
            patcher = mock.patch.object(midtrans, nama, getattr(self.midtrans, nama))
            patcher.start()
            self.addCleanup(patcher.stop)
        for nama in ("get", "post"):
            patcher = mock.patch.object(
                midtrans.requests, nama, side_effect=AssertionError("Tes mencoba menghubungi Midtrans sungguhan.")
            )
            patcher.start()
            self.addCleanup(patcher.stop)


def buat_pembeli(email="pembeli@example.com", **lain):
    lain.setdefault("nama_lengkap", "Pembeli Uji")
    return get_user_model().objects.create_user(email=email, password="x", **lain)


def buat_produk_uji():
    """Satu buku dengan tiga produk siap dibeli: cetak (stok 3), ebook, audiobook (paket siap)."""
    buku = buat_buku("Keamanan Data Modern")
    cetak = buat_produk(buku, Produk.Format.CETAK, 75000, stok=3)
    ebook = buat_produk(buku, Produk.Format.EBOOK, 40000)
    audio = buat_produk(buku, Produk.Format.AUDIOBOOK, 60000)
    PaketAudio.objects.filter(produk=audio).update(status=PaketAudio.Status.SIAP)
    return cetak, ebook, audio
