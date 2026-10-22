from django.test import TestCase, override_settings

from apps.accounts.models import User
from apps.catalog.models import Buku, Produk
from core.testing import STORAGES_MEMORI

from .models import ItemKeranjang, ItemPesanan, Keranjang, Pesanan


@override_settings(STORAGES=STORAGES_MEMORI)
class PesananTests(TestCase):
    def setUp(self):
        self.pembeli = User.objects.create_user(email="pembeli@example.com", password="x", nama_lengkap="Pembeli")
        buku = Buku.objects.create(judul="Buku Uji", penulis="Penulis")
        self.produk = Produk.objects.create(buku=buku, format=Produk.Format.CETAK, harga=75000, stok=10)

    def test_nomor_pesanan_otomatis(self):
        pesanan = Pesanan.objects.create(pembeli=self.pembeli)
        self.assertRegex(pesanan.nomor, r"^PP-\d{8}-[0-9A-F]{6}$")
        self.assertLessEqual(len(pesanan.nomor), 50)  # batas order_id Midtrans

    def test_nomor_pesanan_unik_dan_tidak_berubah(self):
        a = Pesanan.objects.create(pembeli=self.pembeli)
        b = Pesanan.objects.create(pembeli=self.pembeli)
        self.assertNotEqual(a.nomor, b.nomor)
        nomor = a.nomor
        a.save()
        self.assertEqual(a.nomor, nomor)

    def test_status_awal(self):
        pesanan = Pesanan.objects.create(pembeli=self.pembeli)
        self.assertEqual(pesanan.status_pembayaran, Pesanan.StatusPembayaran.MENUNGGU)
        self.assertEqual(pesanan.metode_pengiriman, Pesanan.MetodePengiriman.TANPA)
        self.assertEqual(pesanan.status_pengiriman, Pesanan.StatusPengiriman.TIDAK_ADA)

    def test_subtotal_item(self):
        pesanan = Pesanan.objects.create(pembeli=self.pembeli)
        item = ItemPesanan.objects.create(
            pesanan=pesanan, produk=self.produk, judul="Buku Uji", format="cetak", harga_satuan=75000, jumlah=2
        )
        self.assertEqual(item.subtotal, 150000)

    def test_subtotal_item_keranjang_mengikuti_harga_produk(self):
        keranjang = Keranjang.objects.create(pembeli=self.pembeli)
        item = ItemKeranjang.objects.create(keranjang=keranjang, produk=self.produk, jumlah=3)
        self.assertEqual(item.subtotal, 225000)
