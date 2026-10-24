"""Tes Tahap F: checkout, pengiriman, pemesanan stok, dan transaksi Snap (FR-09–FR-11)."""

from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.catalog.models import Produk
from apps.catalog.testing import buat_buku, buat_produk
from core.testing import STORAGES_MEMORI, berkas_uji

from . import checkout as modul_checkout
from . import midtrans
from .checkout import nama_item
from .keranjang import keranjang_milik
from .models import ItemKeranjang, ItemPesanan, Pesanan
from .testing import PENGATURAN_UJI, MidtransTiruanMixin, buat_pembeli, buat_produk_uji

DELIVERY = {
    "metode_pengiriman": "delivery",
    "nama_penerima": "Siti Aminah",
    "no_telepon_penerima": "0812-3456-7890",
    "alamat": "Perumahan Taman Raya Blok A No. 5",
    "kecamatan": "Batam Kota",
}


@override_settings(STORAGES=STORAGES_MEMORI, **PENGATURAN_UJI)
class CheckoutTestCase(MidtransTiruanMixin, APITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.pembeli = buat_pembeli(no_telepon="0811-1111-2222")
        self.cetak, self.ebook, self.audio = buat_produk_uji()
        self.login(self.pembeli)

    def login(self, pengguna):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(pengguna)}")

    def tambah(self, produk, jumlah=1):
        data = {"produk_id": produk.pk, "jumlah": jumlah}
        response = self.client.post(reverse("keranjang-item"), data, format="json")
        self.assertEqual(response.status_code, 201, response.data)

    def checkout(self, kode=201, **data):
        response = self.client.post(reverse("checkout"), data, format="json")
        self.assertEqual(response.status_code, kode, response.data)
        return response

    def stok_cetak(self):
        return Produk.objects.get(pk=self.cetak.pk).stok


class OpsiCheckoutTests(CheckoutTestCase):
    def test_opsi_pengiriman_dan_isi_keranjang(self):
        self.tambah(self.cetak, 2)
        data = self.client.get(reverse("checkout")).data
        self.assertEqual(data["keranjang"]["total"], 150000)
        self.assertTrue(data["keranjang"]["perlu_pengiriman"])
        self.assertEqual(data["pengiriman"]["delivery"]["ongkir"], 15000)
        self.assertEqual(len(data["pengiriman"]["delivery"]["kecamatan"]), 12)
        self.assertIn("Sekupang", data["pengiriman"]["delivery"]["kecamatan"])
        self.assertEqual(
            data["pengiriman"]["takeaway"],
            {"label": "Takeaway (ambil sendiri)", "ongkir": 0, "lokasi": PENGATURAN_UJI["LOKASI_TAKEAWAY"]},
        )
        self.assertEqual((data["batas_bayar_menit"], data["metode_pembayaran"]), (60, ["other_qris"]))

    def test_perlu_login(self):
        self.client.credentials()
        self.assertEqual(self.client.get(reverse("checkout")).status_code, 401)
        self.assertEqual(self.client.post(reverse("checkout"), {}, format="json").status_code, 401)


class CheckoutDigitalTests(CheckoutTestCase):
    def test_checkout_produk_digital(self):
        self.tambah(self.ebook)
        self.tambah(self.audio)
        sebelum = timezone.now()
        data = self.checkout(**DELIVERY).data  # isian pengiriman diabaikan karena semuanya digital

        pesanan = Pesanan.objects.get(nomor=data["nomor"])
        self.assertEqual(pesanan.pembeli, self.pembeli)
        self.assertEqual(pesanan.status_pembayaran, Pesanan.StatusPembayaran.MENUNGGU)
        self.assertEqual(pesanan.metode_pengiriman, Pesanan.MetodePengiriman.TANPA)
        self.assertEqual(pesanan.status_pengiriman, Pesanan.StatusPengiriman.TIDAK_ADA)
        self.assertEqual((pesanan.subtotal, pesanan.ongkir, pesanan.total), (100000, 0, 100000))
        self.assertEqual(pesanan.alamat_pengiriman, "")
        self.assertAlmostEqual(pesanan.batas_bayar, sebelum + timedelta(minutes=60), delta=timedelta(seconds=5))
        self.assertEqual(pesanan.snap_token, f"token-{pesanan.nomor}")
        self.assertEqual(
            list(pesanan.item.values_list("judul", "format", "harga_satuan", "jumlah")),
            [("Keamanan Data Modern", "ebook", 40000, 1), ("Keamanan Data Modern", "audiobook", 60000, 1)],
        )
        self.assertFalse(ItemKeranjang.objects.exists())  # keranjang dikosongkan

        self.assertEqual(data["pembayaran"]["snap_token"], f"token-{pesanan.nomor}")
        self.assertEqual(data["pembayaran"]["client_key"], PENGATURAN_UJI["MIDTRANS_CLIENT_KEY"])
        self.assertEqual(data["pembayaran"]["snap_js"], "https://app.sandbox.midtrans.com/snap/snap.js")
        self.assertIsNone(data["pengiriman"])
        self.assertNotIn(PENGATURAN_UJI["MIDTRANS_SERVER_KEY"], str(data))

    def test_permintaan_snap(self):
        self.tambah(self.ebook)
        self.checkout()
        pesanan = Pesanan.objects.get()
        payload = self.midtrans.payload_snap[0]
        self.assertEqual(payload["transaction_details"], {"order_id": pesanan.nomor, "gross_amount": 40000})
        self.assertEqual(
            payload["item_details"],
            [{"id": str(self.ebook.pk), "price": 40000, "quantity": 1, "name": "Keamanan Data Modern (Ebook)"}],
        )
        self.assertEqual(
            payload["customer_details"],
            {"first_name": "Pembeli Uji", "email": "pembeli@example.com", "phone": "0811-1111-2222"},
        )
        self.assertEqual(payload["enabled_payments"], ["other_qris"])
        # Kedaluwarsa dihitung sejak checkout dan sama dengan batas_bayar pesanan.
        mulai = timezone.localtime(pesanan.batas_bayar - timedelta(minutes=60))
        self.assertEqual(
            payload["expiry"],
            {"start_time": mulai.strftime("%Y-%m-%d %H:%M:%S +0700"), "unit": "minute", "duration": 60},
        )
        self.assertEqual(payload["page_expiry"], {"duration": 60, "unit": "minute"})

    def test_nama_item_dipotong_50_karakter(self):
        judul = "Panduan  Lengkap Keamanan Informasi untuk Usaha | Kecil dan Menengah"
        item = ItemPesanan(judul=judul, format="audiobook")
        nama = nama_item(item)
        self.assertLessEqual(len(nama), 50)
        self.assertTrue(nama.endswith("... (Audiobook)"))
        self.assertTrue(nama.startswith("Panduan Lengkap Keamanan Informasi"))
        self.assertNotIn("|", nama_item(ItemPesanan(judul="A | B", format="cetak")))


class CheckoutCetakTests(CheckoutTestCase):
    def test_delivery_campuran_ongkir_dan_stok_dipesan(self):
        self.tambah(self.cetak, 2)
        self.tambah(self.ebook)
        data = self.checkout(**DELIVERY).data
        pesanan = Pesanan.objects.get()
        self.assertEqual((pesanan.subtotal, pesanan.ongkir, pesanan.total), (190000, 15000, 205000))
        self.assertEqual(pesanan.metode_pengiriman, Pesanan.MetodePengiriman.DELIVERY)
        self.assertEqual(pesanan.status_pengiriman, Pesanan.StatusPengiriman.MENUNGGU)
        self.assertEqual(pesanan.alamat_pengiriman, "Perumahan Taman Raya Blok A No. 5, Kec. Batam Kota, Kota Batam")
        self.assertEqual((pesanan.nama_penerima, pesanan.no_telepon_penerima), ("Siti Aminah", "0812-3456-7890"))
        self.assertEqual(self.stok_cetak(), 1)  # 3 - 2, dipesan sejak checkout
        rincian = self.midtrans.payload_snap[0]["item_details"]
        ongkir = {"id": "ONGKIR", "price": 15000, "quantity": 1, "name": "Ongkos kirim Kota Batam"}
        self.assertEqual(rincian[-1], ongkir)
        self.assertEqual(sum(i["price"] * i["quantity"] for i in rincian), 205000)
        self.assertEqual(self.midtrans.payload_snap[0]["customer_details"]["first_name"], "Siti Aminah")
        self.assertEqual(
            data["pengiriman"],
            {
                "nama_penerima": "Siti Aminah",
                "no_telepon_penerima": "0812-3456-7890",
                "alamat": "Perumahan Taman Raya Blok A No. 5, Kec. Batam Kota, Kota Batam",
            },
        )
        self.assertEqual(data["ongkir"], 15000)

    def test_takeaway_tanpa_ongkir_dan_memakai_data_profil(self):
        self.tambah(self.cetak)
        data = self.checkout(metode_pengiriman="takeaway").data
        pesanan = Pesanan.objects.get()
        self.assertEqual((pesanan.ongkir, pesanan.total), (0, 75000))
        self.assertEqual((pesanan.nama_penerima, pesanan.no_telepon_penerima), ("Pembeli Uji", "0811-1111-2222"))
        self.assertEqual(pesanan.alamat_pengiriman, "")
        self.assertEqual(data["pengiriman"]["lokasi_pengambilan"], PENGATURAN_UJI["LOKASI_TAKEAWAY"])
        self.assertEqual(len(self.midtrans.payload_snap[0]["item_details"]), 1)  # tanpa baris ongkir

    def test_validasi_isian_pengiriman(self):
        tanpa_telepon = buat_pembeli("tanpa.telepon@example.com")
        self.login(tanpa_telepon)
        self.tambah(self.cetak)
        kasus = [
            ({}, "detail", "Pilih metode pengiriman"),
            ({"metode_pengiriman": "kurir"}, "metode_pengiriman", "delivery atau takeaway"),
            ({"metode_pengiriman": "delivery", "no_telepon_penerima": "08123456789"}, "alamat", "wajib"),
            ({**DELIVERY, "kecamatan": ""}, "kecamatan", "Kota Batam"),
            ({**DELIVERY, "kecamatan": "Tanjungpinang"}, "kecamatan", "Kota Batam"),
            ({"metode_pengiriman": "takeaway"}, "no_telepon_penerima", "wajib"),  # profil tanpa telepon
            ({**DELIVERY, "no_telepon_penerima": "telepon saya"}, "no_telepon_penerima", "angka"),
        ]
        for data, kolom, pesan in kasus:
            with self.subTest(data=data):
                response = self.client.post(reverse("checkout"), data, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn(pesan, str(response.data[kolom]))
        self.assertFalse(Pesanan.objects.exists())
        self.assertEqual(self.stok_cetak(), 3)


class CheckoutDitolakTests(CheckoutTestCase):
    def test_keranjang_kosong(self):
        response = self.checkout(kode=400)
        self.assertEqual(response.data["detail"], "Keranjang kosong.")

    def test_ada_item_tidak_tersedia(self):
        self.tambah(self.cetak, 3)
        self.tambah(self.ebook)
        Produk.objects.filter(pk=self.cetak.pk).update(stok=1)
        response = self.checkout(kode=400, **DELIVERY)
        self.assertIn("Keamanan Data Modern (Buku cetak): Stok tersisa 1", response.data["detail"])
        self.assertFalse(Pesanan.objects.exists())
        self.assertEqual(ItemKeranjang.objects.count(), 2)  # keranjang tetap utuh

    def test_stok_diambil_checkout_lain_di_saat_bersamaan(self):
        # Ringkasan keranjang masih melihat stok 3, tetapi UPDATE bersyarat menolak bila stok sudah habis.
        self.tambah(self.cetak, 2)
        asli = modul_checkout.ringkasan

        def ringkasan_lalu_stok_diambil(keranjang):
            isi = asli(keranjang)
            Produk.objects.filter(pk=self.cetak.pk).update(stok=1)  # pembeli lain checkout lebih dulu
            return isi

        with mock.patch.object(modul_checkout, "ringkasan", ringkasan_lalu_stok_diambil):
            response = self.checkout(kode=400, **DELIVERY)
        self.assertIn("tidak mencukupi", response.data["detail"])
        self.assertFalse(Pesanan.objects.exists())
        self.assertEqual(ItemKeranjang.objects.count(), 1)

    def test_snap_gagal_semua_dibatalkan(self):
        self.tambah(self.cetak, 2)
        self.tambah(self.ebook)
        self.midtrans.gagal = midtrans.GagalMidtrans("Snap API menolak permintaan (HTTP 500)")
        with self.assertLogs("apps.orders.checkout", "ERROR"):
            response = self.checkout(kode=502, **DELIVERY)
        self.assertIn("Keranjang dan stok tidak berubah", response.data["detail"])
        self.assertFalse(Pesanan.objects.exists())
        self.assertEqual(self.stok_cetak(), 3)
        self.assertEqual(ItemKeranjang.objects.count(), 2)

    def test_midtrans_belum_dikonfigurasi(self):
        self.tambah(self.ebook)
        self.midtrans.gagal = midtrans.BelumDikonfigurasi("MIDTRANS_SERVER_KEY belum diisi di .env.")
        with self.assertLogs("apps.orders.checkout", "ERROR"):
            response = self.checkout(kode=503)
        self.assertIn("konfigurasi Midtrans belum lengkap", response.data["detail"])
        self.assertFalse(Pesanan.objects.exists())

    def test_produk_digital_yang_menunggu_pembayaran_tidak_bisa_dibeli_lagi(self):
        self.tambah(self.ebook)
        nomor = self.checkout().data["nomor"]
        response = self.client.post(reverse("keranjang-item"), {"produk_id": self.ebook.pk}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], f"Produk ini sedang menunggu pembayaran di pesanan {nomor}.")
        # Buku cetak yang sama tetap boleh dibeli lagi.
        self.tambah(self.cetak)

    def test_keranjang_menandai_produk_yang_menunggu_pembayaran(self):
        # Misalnya item masuk keranjang sebelum pesanan lain dibuat lewat perangkat lain.
        self.tambah(self.ebook)
        self.checkout()
        ItemKeranjang.objects.create(keranjang=keranjang_milik(self.pembeli), produk=self.ebook)
        data = self.client.get(reverse("keranjang")).data
        self.assertFalse(data["item"][0]["tersedia"])
        self.assertTrue(data["item"][0]["keterangan"].startswith("Menunggu pembayaran (PP-"))
        self.checkout(kode=400)

    def test_pembuatan_pesanan_dibatasi_10_per_menit(self):
        for _ in range(10):
            self.checkout(kode=400)  # keranjang kosong, tetap dihitung
        self.assertEqual(self.client.post(reverse("checkout"), {}, format="json").status_code, 429)
        self.assertEqual(self.client.get(reverse("checkout")).status_code, 200)  # membaca opsi tidak dibatasi


class RiwayatPesananTests(CheckoutTestCase):
    def test_daftar_dan_detail_hanya_milik_sendiri(self):
        self.tambah(self.cetak, 2)
        self.tambah(self.ebook)
        nomor = self.checkout(**DELIVERY).data["nomor"]
        lain = buat_pembeli("lain@example.com")
        self.login(lain)
        self.assertEqual(self.client.get(reverse("pesanan")).data["count"], 0)
        for response in (
            self.client.get(reverse("pesanan-detail", args=[nomor])),
            self.client.post(reverse("pesanan-cek-status", args=[nomor])),
        ):
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.data["detail"], "Pesanan tidak ditemukan.")

        self.login(self.pembeli)
        daftar = self.client.get(reverse("pesanan")).data
        self.assertEqual(daftar["count"], 1)
        baris = daftar["results"][0]
        self.assertEqual((baris["nomor"], baris["total"], baris["jumlah_item"]), (nomor, 205000, 3))
        self.assertEqual(baris["ringkasan"], "Keamanan Data Modern dan 1 produk lain")
        self.assertEqual(baris["status_pembayaran_label"], "Menunggu pembayaran")
        detail = self.client.get(reverse("pesanan-detail", args=[nomor])).data
        self.assertEqual([i["format"] for i in detail["item"]], ["cetak", "ebook"])
        self.assertEqual(detail["item"][0]["subtotal"], 150000)
        self.assertEqual(detail["item"][0]["buku"], {"slug": self.cetak.buku.slug, "sampul": None})
        self.assertIsNotNone(detail["pembayaran"])

    def test_data_pembayaran_tidak_tampil_setelah_batas_bayar(self):
        self.tambah(self.ebook)
        nomor = self.checkout().data["nomor"]
        Pesanan.objects.filter(nomor=nomor).update(batas_bayar=timezone.now() - timedelta(seconds=1))
        self.assertIsNone(self.client.get(reverse("pesanan-detail", args=[nomor])).data["pembayaran"])

    def test_tanpa_kueri_berulang_per_pesanan(self):
        self.tambah(self.ebook)
        self.checkout()
        self.tambah(self.cetak)
        self.checkout(**DELIVERY)
        self.tambah(self.audio)
        self.checkout()
        with self.assertNumQueries(4):  # pengguna (JWT), jumlah pesanan, halaman pesanan, item pesanan
            self.assertEqual(self.client.get(reverse("pesanan")).data["count"], 3)

    def test_detail_memuat_sampul_tanpa_kueri_berulang_per_item(self):
        buku_lain = buat_buku("Jaringan Komputer", sampul=berkas_uji("sampul.jpg"))
        ebook_lain = buat_produk(buku_lain, Produk.Format.EBOOK, 30000)
        self.tambah(self.cetak)
        self.tambah(self.ebook)
        self.tambah(ebook_lain)
        nomor = self.checkout(**DELIVERY).data["nomor"]
        # pengguna (JWT), pesanan, item, produk, buku — tetap 5 berapa pun jumlah itemnya.
        with self.assertNumQueries(5):
            detail = self.client.get(reverse("pesanan-detail", args=[nomor])).data
        buku = [i["buku"] for i in detail["item"]]
        self.assertEqual([b["slug"] for b in buku], [self.cetak.buku.slug, self.cetak.buku.slug, buku_lain.slug])
        self.assertIsNone(buku[0]["sampul"])
        self.assertIn("X-Amz-Expires=3600", buku[2]["sampul"])  # presigned URL sampul seperti di katalog
