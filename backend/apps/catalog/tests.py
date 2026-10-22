from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from core.testing import STORAGES_MEMORI, berkas_uji

from .models import Buku, Kategori, Produk


@override_settings(STORAGES=STORAGES_MEMORI)
class BukuTests(TestCase):
    def test_slug_otomatis_dan_unik(self):
        a = Buku.objects.create(judul="Dasar Kecerdasan Buatan", penulis="A")
        b = Buku.objects.create(judul="Dasar Kecerdasan Buatan", penulis="B")
        self.assertEqual(a.slug, "dasar-kecerdasan-buatan")
        self.assertEqual(b.slug, "dasar-kecerdasan-buatan-2")


@override_settings(STORAGES=STORAGES_MEMORI)
class ProdukTests(TestCase):
    def setUp(self):
        self.buku = Buku.objects.create(judul="Buku Uji", penulis="Penulis Uji")

    def produk(self, **kwargs):
        data = {"buku": self.buku, "format": Produk.Format.CETAK, "harga": 50000}
        data.update(kwargs)
        return Produk(**data)

    def test_buku_cetak_valid_tanpa_berkas(self):
        self.produk(stok=5).full_clean()

    def test_buku_cetak_tidak_boleh_berkas(self):
        p = self.produk(berkas=berkas_uji("buku.pdf"))
        with self.assertRaises(ValidationError) as ctx:
            p.full_clean()
        self.assertIn("berkas", ctx.exception.message_dict)

    def test_produk_digital_wajib_berkas(self):
        for fmt in (Produk.Format.EBOOK, Produk.Format.AUDIOBOOK):
            with self.subTest(fmt=fmt), self.assertRaises(ValidationError) as ctx:
                self.produk(format=fmt).full_clean()
            self.assertIn("berkas", ctx.exception.message_dict)

    def test_ekstensi_berkas_harus_sesuai_format(self):
        kasus = [
            (Produk.Format.EBOOK, "buku.pdf", True),
            (Produk.Format.EBOOK, "buku.mp3", False),
            (Produk.Format.AUDIOBOOK, "audio.mp3", True),
            (Produk.Format.AUDIOBOOK, "audio.PDF", False),
        ]
        for fmt, nama, valid in kasus:
            with self.subTest(fmt=fmt, nama=nama):
                p = self.produk(format=fmt, berkas=berkas_uji(nama))
                if valid:
                    p.full_clean()
                else:
                    with self.assertRaises(ValidationError):
                        p.full_clean()

    def test_stok_hanya_untuk_buku_cetak(self):
        p = self.produk(format=Produk.Format.EBOOK, berkas=berkas_uji("buku.pdf"), stok=3)
        with self.assertRaises(ValidationError) as ctx:
            p.full_clean()
        self.assertIn("stok", ctx.exception.message_dict)

    def test_harga_minimal_satu_rupiah(self):
        with self.assertRaises(ValidationError) as ctx:
            self.produk(harga=0).full_clean()
        self.assertIn("harga", ctx.exception.message_dict)

    def test_satu_format_per_buku(self):
        self.produk().save()
        with self.assertRaises(IntegrityError):
            self.produk().save()

    def test_berkas_asli_disimpan_dengan_nama_acak(self):
        p = self.produk(format=Produk.Format.EBOOK, berkas=berkas_uji("Rahasia Judul Asli.pdf"))
        p.save()
        self.assertRegex(p.berkas.name, r"^asli/ebook/[0-9a-f]{32}\.pdf$")
        self.assertNotIn("Rahasia", p.berkas.name)

    def test_is_digital(self):
        self.assertFalse(self.produk().is_digital)
        self.assertTrue(self.produk(format=Produk.Format.AUDIOBOOK).is_digital)


@override_settings(STORAGES=STORAGES_MEMORI)
class AdminTombolTests(TestCase):
    """Formulir Kategori dan Buku hanya punya satu tombol simpan dengan label sesuai konteks."""

    def setUp(self):
        admin = User.objects.create_superuser(email="admin@example.com", password="x", nama_lengkap="Admin")
        self.client.force_login(admin)

    def assert_satu_tombol(self, response, label):
        self.assertContains(response, f'value="{label}"')
        self.assertNotContains(response, 'name="_addanother"')
        self.assertNotContains(response, 'name="_continue"')

    def test_halaman_tambah_buku(self):
        response = self.client.get(reverse("admin:catalog_buku_add"))
        self.assert_satu_tombol(response, "Tambah")
        # Tautan baris produk berbunyi "Tambah", bukan "Tambahkan Produk lagi"
        self.assertContains(response, "&quot;addText&quot;: &quot;Tambah&quot;")

    def test_halaman_ubah_buku(self):
        buku = Buku.objects.create(judul="Buku Uji", penulis="Penulis")
        response = self.client.get(reverse("admin:catalog_buku_change", args=[buku.pk]))
        self.assert_satu_tombol(response, "Simpan Perubahan")

    def test_halaman_tambah_dan_ubah_kategori(self):
        self.assert_satu_tombol(self.client.get(reverse("admin:catalog_kategori_add")), "Tambah")
        kategori = Kategori.objects.create(nama="Teknik", slug="teknik")
        response = self.client.get(reverse("admin:catalog_kategori_change", args=[kategori.pk]))
        self.assert_satu_tombol(response, "Simpan Perubahan")
