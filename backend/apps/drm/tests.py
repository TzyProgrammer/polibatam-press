from datetime import timedelta

from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.models import Buku, Produk
from apps.orders.models import ItemPesanan, Pesanan
from core.testing import RAHASIA_UJI, STORAGES_MEMORI, berkas_uji

from .kode import POLA_KODE, buat_kode_watermark, hash_token, kode_cocok
from .models import HakAkses, PaketAudio, SalinanEbook, SesiStreaming


@override_settings(WATERMARK_SECRET=RAHASIA_UJI)
class KodeWatermarkTests(SimpleTestCase):
    def test_format_kode(self):
        self.assertRegex(buat_kode_watermark(1, 2, 3), POLA_KODE)

    def test_kode_deterministik_dan_berbeda_per_pembelian(self):
        self.assertEqual(buat_kode_watermark(1, 2, 3), buat_kode_watermark(1, 2, 3))
        self.assertNotEqual(buat_kode_watermark(1, 2, 3), buat_kode_watermark(1, 2, 4))
        self.assertNotEqual(buat_kode_watermark(1, 2, 3), buat_kode_watermark(9, 2, 3))

    def test_kode_bergantung_pada_rahasia(self):
        kode = buat_kode_watermark(1, 2, 3)
        with self.settings(WATERMARK_SECRET="rahasia-lain"):
            self.assertNotEqual(buat_kode_watermark(1, 2, 3), kode)

    def test_kode_cocok(self):
        kode = buat_kode_watermark(1, 2, 3)
        self.assertTrue(kode_cocok(kode, 1, 2, 3))
        self.assertFalse(kode_cocok(kode, 1, 2, 4))

    def test_tanpa_rahasia_ditolak(self):
        with self.settings(WATERMARK_SECRET=""), self.assertRaises(ImproperlyConfigured):
            buat_kode_watermark(1, 2, 3)

    def test_hash_token(self):
        h = hash_token("token-rahasia")
        self.assertEqual(len(h), 64)
        self.assertNotIn("token-rahasia", h)
        self.assertEqual(h, hash_token("token-rahasia"))


@override_settings(STORAGES=STORAGES_MEMORI, WATERMARK_SECRET=RAHASIA_UJI)
class ModelDRMTests(TestCase):
    def setUp(self):
        self.pembeli = User.objects.create_user(email="pembeli@example.com", password="x", nama_lengkap="Pembeli")
        buku = Buku.objects.create(judul="Buku Uji", penulis="Penulis")
        self.ebook = Produk.objects.create(
            buku=buku, format=Produk.Format.EBOOK, harga=40000, berkas=berkas_uji("buku.pdf")
        )
        self.audiobook = Produk.objects.create(
            buku=buku, format=Produk.Format.AUDIOBOOK, harga=60000, berkas=berkas_uji("audio.mp3")
        )
        self.pesanan = Pesanan.objects.create(pembeli=self.pembeli)
        self.item = ItemPesanan.objects.create(
            pesanan=self.pesanan, produk=self.ebook, judul="Buku Uji", format="ebook", harga_satuan=40000
        )
        self.hak = HakAkses.objects.create(pembeli=self.pembeli, produk=self.ebook, item_pesanan=self.item)

    def test_salinan_ebook_mendapat_kode_watermark_otomatis(self):
        salinan = SalinanEbook.objects.create(hak_akses=self.hak)
        self.assertRegex(salinan.kode_watermark, POLA_KODE)
        self.assertTrue(kode_cocok(salinan.kode_watermark, self.pembeli.pk, self.item.pk, self.ebook.pk))
        self.assertEqual(salinan.status, SalinanEbook.Status.MENUNGGU)

    def test_hak_akses_unik_per_pembeli_dan_produk(self):
        item_lain = ItemPesanan.objects.create(
            pesanan=self.pesanan, produk=self.ebook, judul="Buku Uji", format="ebook", harga_satuan=40000
        )
        with self.assertRaises(IntegrityError):
            HakAkses.objects.create(pembeli=self.pembeli, produk=self.ebook, item_pesanan=item_lain)

    def test_masa_berlaku_sesi_streaming(self):
        paket = self.audiobook.paket_audio  # dibuat otomatis saat MP3 diunggah (Tahap B)
        sesi = SesiStreaming.objects.create(
            pembeli=self.pembeli, paket=paket, token_hash=hash_token("a"),
            kedaluwarsa=timezone.now() + timedelta(minutes=10),
        )
        self.assertTrue(sesi.masih_berlaku)
        sesi.kedaluwarsa = timezone.now() - timedelta(seconds=1)
        self.assertFalse(sesi.masih_berlaku)
        sesi.kedaluwarsa = timezone.now() + timedelta(minutes=10)
        sesi.dicabut = True
        self.assertFalse(sesi.masih_berlaku)

    def test_paket_audio_awal_menunggu_tanpa_kunci(self):
        paket = PaketAudio.objects.get(produk=self.audiobook)
        self.assertEqual(paket.status, PaketAudio.Status.MENUNGGU)
        self.assertEqual(paket.berkas_sumber, self.audiobook.berkas.name)
        self.assertIsNone(paket.kunci_terenkripsi)
