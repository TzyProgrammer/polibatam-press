"""Tes Tahap F: klien Midtrans (Snap API, Status API, tanda tangan notifikasi)."""

import base64
import hashlib
from unittest import mock

import requests
from django.core import checks
from django.test import SimpleTestCase, override_settings

from . import midtrans
from .checks import periksa_pengaturan_pembayaran
from .testing import PENGATURAN_UJI

KUNCI = PENGATURAN_UJI["MIDTRANS_SERVER_KEY"]


def respons(kode, data=None, teks=None):
    hasil = mock.Mock(status_code=kode)
    if data is None:
        hasil.json.side_effect = ValueError("bukan JSON")
    else:
        hasil.json.return_value = data
    hasil.text = teks or ""
    return hasil


@override_settings(**PENGATURAN_UJI)
class KlienMidtransTests(SimpleTestCase):
    def test_snap_memakai_basic_auth_server_key_dan_batas_waktu(self):
        berhasil = respons(201, {"token": "t", "redirect_url": "u"})
        with mock.patch.object(midtrans.requests, "post", return_value=berhasil) as post:
            self.assertEqual(midtrans.buat_transaksi_snap({"a": 1}), {"token": "t", "redirect_url": "u"})
        url = post.call_args.args[0]
        self.assertEqual(url, "https://app.sandbox.midtrans.com/snap/v1/transactions")
        header = post.call_args.kwargs["headers"]
        self.assertEqual(header["Authorization"], "Basic " + base64.b64encode(f"{KUNCI}:".encode()).decode())
        self.assertEqual(post.call_args.kwargs["json"], {"a": 1})
        self.assertEqual(post.call_args.kwargs["timeout"], midtrans.BATAS_WAKTU)

    @override_settings(MIDTRANS_IS_PRODUCTION=True)
    def test_alamat_produksi(self):
        self.assertEqual(midtrans.alamat_layanan(), ("https://app.midtrans.com", "https://api.midtrans.com"))
        self.assertEqual(midtrans.url_snap_js(), "https://app.midtrans.com/snap/snap.js")

    def test_snap_ditolak_atau_tidak_terhubung(self):
        kasus = [
            respons(401, {"error_messages": ["Access denied, please check client or server key"]}),
            respons(400, {"error_messages": ["transaction_details.gross_amount is not equal to the sum of items"]}),
            respons(500, None),
            respons(201, {"redirect_url": "u"}),  # tanpa token
        ]
        for hasil in kasus:
            with self.subTest(kode=hasil.status_code):
                with mock.patch.object(midtrans.requests, "post", return_value=hasil):
                    with self.assertRaises(midtrans.GagalMidtrans) as konteks:
                        midtrans.buat_transaksi_snap({})
                self.assertNotIn(KUNCI, str(konteks.exception))
        with mock.patch.object(midtrans.requests, "post", side_effect=requests.ConnectTimeout("habis waktu")):
            with self.assertRaisesMessage(midtrans.GagalMidtrans, "ConnectTimeout"):
                midtrans.buat_transaksi_snap({})

    @override_settings(MIDTRANS_SERVER_KEY="")
    def test_tanpa_server_key_tidak_mengirim_permintaan(self):
        with mock.patch.object(midtrans.requests, "post") as post, mock.patch.object(midtrans.requests, "get") as get:
            with self.assertRaises(midtrans.BelumDikonfigurasi):
                midtrans.buat_transaksi_snap({})
            with self.assertRaises(midtrans.BelumDikonfigurasi):
                midtrans.status_transaksi("PP-1")
        post.assert_not_called()
        get.assert_not_called()

    def test_status_api(self):
        data = {"status_code": "200", "transaction_status": "settlement", "order_id": "PP-20261022-ABC123"}
        with mock.patch.object(midtrans.requests, "get", return_value=respons(200, data)) as get:
            self.assertEqual(midtrans.status_transaksi("PP-20261022-ABC123"), data)
        self.assertEqual(get.call_args.args[0], "https://api.sandbox.midtrans.com/v2/PP-20261022-ABC123/status")

    def test_status_api_transaksi_belum_ada(self):
        tidak_ada = {"status_code": "404", "status_message": "The requested resource is not found"}
        for hasil in (respons(404, tidak_ada), respons(200, tidak_ada), respons(404, None)):
            with self.subTest(http=hasil.status_code), mock.patch.object(midtrans.requests, "get", return_value=hasil):
                self.assertIsNone(midtrans.status_transaksi("PP-1"))

    def test_status_api_error_bukan_404(self):
        for hasil in (
            respons(200, {"status_code": "401", "status_message": "Unknown Merchant server_key/id"}),
            respons(500, None),
            respons(503, {"status_code": "503"}),
        ):
            with self.subTest(http=hasil.status_code), mock.patch.object(midtrans.requests, "get", return_value=hasil):
                with self.assertRaises(midtrans.GagalMidtrans):
                    midtrans.status_transaksi("PP-1")


@override_settings(**PENGATURAN_UJI)
class TandaTanganTests(SimpleTestCase):
    def notifikasi(self, **lain):
        data = {"order_id": "PP-20261022-ABC123", "status_code": "200", "gross_amount": "130000.00"}
        teks = data["order_id"] + data["status_code"] + data["gross_amount"] + KUNCI
        data["signature_key"] = hashlib.sha512(teks.encode()).hexdigest()
        data.update(lain)
        return data

    def test_tanda_tangan_sha512_sesuai_dokumentasi(self):
        self.assertTrue(midtrans.tanda_tangan_valid(self.notifikasi()))

    def test_tanda_tangan_salah_atau_isi_diubah(self):
        for ubahan in (
            {"signature_key": "0" * 128},
            {"gross_amount": "1.00"},  # nominal diubah setelah ditandatangani
            {"status_code": "201"},
            {"order_id": "PP-20261022-XXXXXX"},
            {"signature_key": None},
            {"gross_amount": 130000},  # bukan string
            {"signature_key": "é" * 128},
        ):
            with self.subTest(ubahan=ubahan):
                self.assertFalse(midtrans.tanda_tangan_valid(self.notifikasi(**ubahan)))
        self.assertFalse(midtrans.tanda_tangan_valid(["bukan", "objek"]))

    def test_tanpa_server_key_semua_notifikasi_ditolak(self):
        data = {"order_id": "PP-1", "status_code": "200", "gross_amount": "1.00"}
        # Tanda tangan dengan server key kosong bisa dibuat siapa saja.
        data["signature_key"] = hashlib.sha512(b"PP-12001.00").hexdigest()
        with override_settings(MIDTRANS_SERVER_KEY=""):
            self.assertFalse(midtrans.tanda_tangan_valid(data))


class PemeriksaanPengaturanTests(SimpleTestCase):
    def kode_peringatan(self, **pengaturan):
        with override_settings(**{**PENGATURAN_UJI, **pengaturan}):
            return [peringatan.id for peringatan in periksa_pengaturan_pembayaran(None)]

    def test_pengaturan_lengkap_tanpa_peringatan(self):
        self.assertEqual(self.kode_peringatan(), [])

    def test_peringatan_pengaturan_belum_siap(self):
        self.assertEqual(
            self.kode_peringatan(
                MIDTRANS_SERVER_KEY="", MIDTRANS_CLIENT_KEY="", MIDTRANS_IS_PRODUCTION=True, BATAS_BAYAR_MENIT=0,
                ONGKIR_KOTA_BATAM=-1,
            ),
            ["orders.W001", "orders.W002", "orders.W003", "orders.W004", "orders.W005"],
        )

    def test_pemeriksaan_terdaftar(self):
        # Ikut dijalankan oleh "manage.py check" dan saat runserver mulai.
        with override_settings(**{**PENGATURAN_UJI, "MIDTRANS_SERVER_KEY": ""}):
            self.assertIn("orders.W001", [p.id for p in checks.run_checks()])
