"""Tes Tahap E: API keranjang campuran (FR-08)."""

from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import User
from apps.catalog.models import Produk
from apps.catalog.testing import buat_buku, buat_produk
from apps.drm.models import HakAkses, PaketAudio
from core.testing import STORAGES_MEMORI

from .models import ItemKeranjang, ItemPesanan, Pesanan


@override_settings(STORAGES=STORAGES_MEMORI)
class KeranjangTestCase(APITestCase):
    def setUp(self):
        self.pembeli = User.objects.create_user(email="pembeli@example.com", password="x", nama_lengkap="Pembeli")
        self.lain = User.objects.create_user(email="lain@example.com", password="x", nama_lengkap="Lain")
        buku = buat_buku("Keamanan Data Modern")
        self.cetak = buat_produk(buku, Produk.Format.CETAK, 75000, stok=3)
        self.ebook = buat_produk(buku, Produk.Format.EBOOK, 40000)
        self.audio = buat_produk(buku, Produk.Format.AUDIOBOOK, 60000)
        PaketAudio.objects.filter(produk=self.audio).update(status=PaketAudio.Status.SIAP)
        buku_lain = buat_buku("Audiobook Belum Siap")
        self.audio_belum_siap = buat_produk(buku_lain, Produk.Format.AUDIOBOOK, 55000)
        self.cetak_habis = buat_produk(buku_lain, Produk.Format.CETAK, 50000, stok=0)
        self.login(self.pembeli)

    def login(self, pengguna):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(pengguna)}")

    def tambah(self, produk, jumlah=1, kode=201):
        data = {"produk_id": produk.pk, "jumlah": jumlah}
        response = self.client.post(reverse("keranjang-item"), data, format="json")
        self.assertEqual(response.status_code, kode, response.data)
        return response

    def item_id(self, produk):
        return ItemKeranjang.objects.get(keranjang__pembeli=self.pembeli, produk=produk).pk

    def beri_hak_akses(self, produk):
        pesanan = Pesanan.objects.create(pembeli=self.pembeli, status_pembayaran=Pesanan.StatusPembayaran.LUNAS)
        item = ItemPesanan.objects.create(
            pesanan=pesanan, produk=produk, judul=produk.buku.judul, format=produk.format, harga_satuan=produk.harga
        )
        HakAkses.objects.create(pembeli=self.pembeli, produk=produk, item_pesanan=item)


class IsiKeranjangTests(KeranjangTestCase):
    def test_keranjang_kosong_dibuat_otomatis(self):
        response = self.client.get(reverse("keranjang"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {"item": [], "jumlah_item": 0, "total": 0, "perlu_pengiriman": False, "semua_tersedia": True},
        )

    def test_keranjang_campuran(self):
        self.tambah(self.cetak, 2)
        self.tambah(self.ebook)
        data = self.tambah(self.audio).data
        self.assertEqual([i["produk"]["format"] for i in data["item"]], ["cetak", "ebook", "audiobook"])
        self.assertEqual(data["jumlah_item"], 4)
        self.assertEqual(data["total"], 2 * 75000 + 40000 + 60000)
        self.assertTrue(data["perlu_pengiriman"])
        cetak = data["item"][0]
        self.assertEqual((cetak["jumlah"], cetak["subtotal"], cetak["produk"]["stok"]), (2, 150000, 3))
        self.assertEqual(cetak["produk"]["buku"]["judul"], "Keamanan Data Modern")
        self.assertIsNone(data["item"][1]["produk"]["stok"])

    def test_hanya_produk_digital_tidak_perlu_pengiriman(self):
        self.assertFalse(self.tambah(self.ebook).data["perlu_pengiriman"])

    def test_keranjang_milik_masing_masing_dan_perlu_login(self):
        self.tambah(self.cetak)
        self.login(self.lain)
        self.assertEqual(self.client.get(reverse("keranjang")).data["item"], [])
        self.client.credentials()
        self.assertEqual(self.client.get(reverse("keranjang")).status_code, 401)
        self.assertEqual(self.client.post(reverse("keranjang-item"), {"produk_id": self.cetak.pk}).status_code, 401)


class TambahItemTests(KeranjangTestCase):
    def pesan_gagal(self, produk_id, jumlah=1):
        data = {"produk_id": produk_id, "jumlah": jumlah}
        response = self.client.post(reverse("keranjang-item"), data, format="json")
        self.assertEqual(response.status_code, 400)
        return response.data["detail"]

    def test_buku_cetak_dijumlahkan_sampai_batas_stok(self):
        self.tambah(self.cetak, 2)
        self.assertEqual(self.tambah(self.cetak, 1).data["item"][0]["jumlah"], 3)
        self.assertEqual(self.pesan_gagal(self.cetak.pk), "Stok tidak mencukupi. Tersisa 3.")

    def test_aturan_produk_digital(self):
        self.assertEqual(self.pesan_gagal(self.ebook.pk, 2), "Produk digital hanya bisa dibeli satu kali (jumlah 1).")
        self.tambah(self.ebook)
        self.assertEqual(self.pesan_gagal(self.ebook.pk), "Produk ini sudah ada di keranjang.")
        self.beri_hak_akses(self.audio)
        self.assertEqual(self.pesan_gagal(self.audio.pk), "Anda sudah memiliki produk ini. Buka di Koleksi.")

    def test_produk_tidak_tersedia(self):
        self.ebook.aktif = False
        self.ebook.save()
        for produk_id, pesan in (
            (self.ebook.pk, "Produk tidak tersedia: tidak dijual."),
            (self.audio_belum_siap.pk, "Produk tidak tersedia: sedang disiapkan."),
            (self.cetak_habis.pk, "Produk tidak tersedia: stok habis."),
            (999999, "Produk tidak ditemukan."),
        ):
            with self.subTest(pesan=pesan):
                self.assertEqual(self.pesan_gagal(produk_id), pesan)
        self.assertFalse(ItemKeranjang.objects.exists())

    def test_isian_tidak_valid(self):
        response = self.client.post(reverse("keranjang-item"), {"jumlah": 0}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.data), {"produk_id", "jumlah"})


class UbahHapusItemTests(KeranjangTestCase):
    def url(self, item_id):
        return reverse("keranjang-item-detail", args=[item_id])

    def test_ubah_jumlah_buku_cetak(self):
        self.tambah(self.cetak)
        item = self.item_id(self.cetak)
        response = self.client.patch(self.url(item), {"jumlah": 3}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["item"][0]["jumlah"], 3)
        response = self.client.patch(self.url(item), {"jumlah": 4}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Stok tidak mencukupi. Tersisa 3.")

    def test_jumlah_produk_digital_tetap_satu(self):
        self.tambah(self.ebook)
        response = self.client.patch(self.url(self.item_id(self.ebook)), {"jumlah": 2}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Jumlah produk digital selalu 1.")

    def test_hapus_item(self):
        self.tambah(self.cetak)
        self.tambah(self.ebook)
        item = self.item_id(self.cetak)
        response = self.client.delete(self.url(item))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([i["produk"]["format"] for i in response.data["item"]], ["ebook"])
        self.assertEqual(self.client.delete(self.url(item)).status_code, 404)

    def test_item_milik_orang_lain_tidak_bisa_diubah(self):
        self.tambah(self.cetak)
        item = self.item_id(self.cetak)
        self.login(self.lain)
        ubah = self.client.patch(self.url(item), {"jumlah": 2}, format="json")
        for response in (ubah, self.client.delete(self.url(item))):
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.data["detail"], "Item keranjang tidak ditemukan.")
        self.assertEqual(ItemKeranjang.objects.get(pk=item).jumlah, 1)


class StatusItemTests(KeranjangTestCase):
    def test_item_yang_berubah_tidak_tersedia_tidak_dihitung(self):
        self.tambah(self.cetak, 3)
        self.tambah(self.ebook)
        self.tambah(self.audio)
        Produk.objects.filter(pk=self.cetak.pk).update(stok=1)
        Produk.objects.filter(pk=self.audio.pk).update(aktif=False)
        self.beri_hak_akses(self.ebook)  # misalnya dibeli lewat pesanan lain
        data = self.client.get(reverse("keranjang")).data
        status = {i["produk"]["format"]: (i["tersedia"], i["keterangan"]) for i in data["item"]}
        self.assertEqual(
            status,
            {
                "cetak": (False, "Stok tersisa 1"),
                "ebook": (False, "Sudah dimiliki"),
                "audiobook": (False, "Tidak dijual"),
            },
        )
        self.assertEqual(data["total"], 0)
        self.assertFalse(data["semua_tersedia"])
