"""Tes formulir Buku di Django Admin: data wajib, minimal satu produk, dan tombol Hapus (revisi Tahap R)."""

from unittest import mock

from django.contrib.admin.models import LogEntry
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.drm.models import PaketAudio
from apps.drm.tasks import kemas_audiobook
from apps.orders.models import ItemPesanan, Pesanan
from core.testing import STORAGES_MEMORI, berkas_uji

from .models import Buku, Kategori, Produk
from .testing import buat_buku, buat_produk

PESAN_MINIMAL_PRODUK = "Tambahkan minimal 1 produk (buku cetak, ebook, atau audiobook) sebelum menyimpan buku."


def baris_cetak(**ubah):
    return {"format": "cetak", "harga": "85000", "stok": "10", "aktif": "on", **ubah}


def baris_ebook(**ubah):
    return {
        "format": "ebook",
        "harga": "45000",
        "stok": "0",
        "berkas": berkas_uji("naskah.pdf", b"%PDF-1.4 uji", "application/pdf"),
        "aktif": "on",
        **ubah,
    }


def baris_audiobook(**ubah):
    return {
        "format": "audiobook",
        "harga": "55000",
        "stok": "0",
        "berkas": berkas_uji("rekaman.mp3", b"ID3 uji", "audio/mpeg"),
        "aktif": "on",
        **ubah,
    }


@override_settings(STORAGES=STORAGES_MEMORI)
class FormulirTambahBukuTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email="admin@example.com", password="x", nama_lengkap="Admin")
        self.client.force_login(self.admin)
        self.kategori = Kategori.objects.create(nama="Teknik", slug="teknik")

    def data_buku(self, produk=(), **ubah):
        data = {
            "judul": "Rekayasa Perangkat Lunak",
            "slug": "",
            "penulis": "Penulis Uji",
            "sinopsis": "Sinopsis singkat.",
            "kategori": str(self.kategori.pk),
            "isbn": "978-623-00-0000-1",
            "tahun_terbit": "2025",
            "jumlah_halaman": "180",
            "ukuran": "14,8 x 21 cm",
            "sampul": berkas_uji("sampul.jpg", b"gambar", "image/jpeg"),
            "aktif": "on",
            "produk-TOTAL_FORMS": str(len(produk)),
            "produk-INITIAL_FORMS": "0",
            "produk-MIN_NUM_FORMS": "1",
            "produk-MAX_NUM_FORMS": "3",
        }
        for i, baris in enumerate(produk):
            for kunci, nilai in baris.items():
                data[f"produk-{i}-{kunci}"] = nilai
        data.update(ubah)
        return data

    def kirim(self, data):
        with mock.patch.object(kemas_audiobook, "delay"):
            return self.client.post(reverse("admin:catalog_buku_add"), data)

    def test_halaman_tambah_langsung_menampilkan_satu_baris_produk(self):
        response = self.client.get(reverse("admin:catalog_buku_add"))
        self.assertContains(response, '<input type="hidden" name="produk-TOTAL_FORMS" value="1" id="id_produk-TOTAL_FORMS">', html=True)
        self.assertContains(response, '<input type="hidden" name="produk-MAX_NUM_FORMS" value="3" id="id_produk-MAX_NUM_FORMS">', html=True)
        # Penghapusan tidak lewat kotak centang: tidak ada kolom DELETE.
        self.assertNotContains(response, "produk-0-DELETE")
        self.assertContains(response, "polibatam/admin-buku.js")
        self.assertContains(response, "polibatam/admin-modal.js")

    def test_data_buku_wajib_diisi(self):
        kosong = {nama: "" for nama in ("judul", "penulis", "sinopsis", "kategori", "isbn", "tahun_terbit")}
        data = self.data_buku([baris_cetak()], **kosong)
        del data["sampul"]
        response = self.kirim(data)
        self.assertEqual(response.status_code, 200)
        galat = response.context["adminform"].form.errors
        for nama in ("judul", "penulis", "sinopsis", "kategori", "isbn", "tahun_terbit", "sampul"):
            self.assertIn(nama, galat, nama)
        self.assertFalse(Buku.objects.exists())

    def test_buku_tanpa_produk_ditolak(self):
        response = self.kirim(self.data_buku([]))
        self.assertEqual(response.status_code, 200)
        formset = response.context["inline_admin_formsets"][0].formset
        self.assertEqual(formset.non_form_errors(), [PESAN_MINIMAL_PRODUK])
        self.assertContains(response, PESAN_MINIMAL_PRODUK)
        self.assertFalse(Buku.objects.exists())

    def test_baris_produk_kosong_ditolak(self):
        response = self.kirim(self.data_buku([{"format": "", "harga": "", "stok": "0"}]))
        self.assertEqual(response.status_code, 200)
        formset = response.context["inline_admin_formsets"][0].formset
        self.assertIn("format", formset.forms[0].errors)
        self.assertFalse(Buku.objects.exists())

    def test_halaman_dan_ukuran_wajib_untuk_cetak_atau_ebook(self):
        for baris in (baris_cetak, baris_ebook):
            with self.subTest(format=baris()["format"]):
                response = self.kirim(self.data_buku([baris()], jumlah_halaman="", ukuran=""))
                self.assertEqual(response.status_code, 200)
                galat = response.context["adminform"].form.errors
                self.assertEqual(
                    galat["jumlah_halaman"],
                    ["Jumlah halaman wajib diisi untuk buku yang memiliki produk cetak atau ebook."],
                )
                self.assertEqual(galat["ukuran"], ["Ukuran wajib diisi untuk buku yang memiliki produk cetak atau ebook."])
        self.assertFalse(Buku.objects.exists())

    def test_audiobook_saja_tidak_wajib_halaman_dan_ukuran(self):
        response = self.kirim(self.data_buku([baris_audiobook()], jumlah_halaman="", ukuran=""))
        self.assertRedirects(response, reverse("admin:catalog_buku_changelist"), fetch_redirect_response=False)
        buku = Buku.objects.get()
        self.assertIsNone(buku.jumlah_halaman)
        self.assertEqual(buku.produk.get().format, Produk.Format.AUDIOBOOK)

    def test_tambah_buku_lengkap_dan_stok_produk_digital_selalu_nol(self):
        response = self.kirim(self.data_buku([baris_cetak(stok="12"), baris_ebook(stok="7")]))
        self.assertRedirects(response, reverse("admin:catalog_buku_changelist"), fetch_redirect_response=False)
        buku = Buku.objects.get()
        self.assertEqual(buku.judul, "Rekayasa Perangkat Lunak")
        self.assertTrue(buku.sampul.name.startswith("sampul/"))
        produk = {p.format: p for p in buku.produk.all()}
        self.assertEqual(produk["cetak"].stok, 12)
        self.assertEqual(produk["ebook"].stok, 0)
        self.assertTrue(produk["ebook"].berkas.name.startswith("asli/ebook/"))

    def test_format_ganda_ditolak(self):
        response = self.kirim(self.data_buku([baris_cetak(), baris_cetak(harga="90000")]))
        self.assertEqual(response.status_code, 200)
        formset = response.context["inline_admin_formsets"][0].formset
        self.assertEqual(formset.non_form_errors(), ["Setiap format hanya boleh satu kali per buku."])
        self.assertFalse(Buku.objects.exists())

    def test_berkas_buku_cetak_ditolak(self):
        # Kolom berkas buku cetak dikunci di halaman, tetapi server tetap menolak bila dikirim paksa.
        baris = baris_cetak(berkas=berkas_uji("naskah.pdf", b"%PDF", "application/pdf"))
        response = self.kirim(self.data_buku([baris]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("berkas", response.context["inline_admin_formsets"][0].formset.forms[0].errors)


@override_settings(STORAGES=STORAGES_MEMORI)
class TombolHapusProdukTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email="admin@example.com", password="x", nama_lengkap="Admin")
        self.client.force_login(self.admin)
        self.buku = buat_buku("Moby Dick", jumlah_halaman=300, ukuran="14 x 20 cm")
        self.cetak = buat_produk(self.buku, Produk.Format.CETAK, 90000, stok=5)
        self.ebook = buat_produk(self.buku, Produk.Format.EBOOK, 40000)

    def url_hapus_berkas(self, produk):
        return reverse("admin:catalog_produk_hapus_berkas", args=[produk.pk])

    def url_hapus_produk(self, produk):
        return reverse("admin:catalog_produk_hapus", args=[produk.pk])

    def test_halaman_ubah_menampilkan_tombol_hapus_tanpa_kotak_centang(self):
        response = self.client.get(reverse("admin:catalog_buku_change", args=[self.buku.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'data-hapus-produk="{self.url_hapus_produk(self.cetak)}"')
        self.assertContains(response, f'data-hapus-produk="{self.url_hapus_produk(self.ebook)}"')
        self.assertContains(response, f'data-hapus-berkas="{self.url_hapus_berkas(self.ebook)}"')
        self.assertNotContains(response, f'data-hapus-berkas="{self.url_hapus_berkas(self.cetak)}"')
        self.assertNotContains(response, "-DELETE")
        self.assertNotContains(response, "berkas-clear")

    def test_hapus_berkas_ebook(self):
        nama = self.ebook.berkas.name
        self.assertTrue(default_storage.exists(nama))
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url_hapus_berkas(self.ebook))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["pesan"], "Berkas Ebook (PDF) untuk “Moby Dick” dihapus.")
        self.ebook.refresh_from_db()
        self.assertEqual(self.ebook.berkas.name, "")
        self.assertFalse(default_storage.exists(nama))
        log = LogEntry.objects.get(object_id=str(self.buku.pk))
        self.assertEqual(log.change_message, "Berkas Ebook (PDF) untuk “Moby Dick” dihapus.")
        # Pesan sukses tampil setelah halaman dimuat ulang.
        halaman = self.client.get(reverse("admin:catalog_buku_change", args=[self.buku.pk]))
        self.assertContains(halaman, "Berkas Ebook (PDF) untuk “Moby Dick” dihapus.")

    def test_hapus_berkas_audiobook_ikut_menghapus_paket_hls(self):
        audio = buat_produk(self.buku, Produk.Format.AUDIOBOOK, 50000)
        paket = PaketAudio.objects.get(produk=audio)
        paket.prefix_hls = f"hls/{paket.pk}"
        paket.save()
        default_storage.save(f"hls/{paket.pk}/segmen0.ts", berkas_uji("segmen0.ts"))
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url_hapus_berkas(audio))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PaketAudio.objects.filter(produk=audio).exists())
        self.assertFalse(default_storage.exists(f"hls/{paket.pk}/segmen0.ts"))
        audio.refresh_from_db()
        self.assertEqual(audio.berkas.name, "")

    def test_hapus_berkas_tanpa_berkas_ditolak(self):
        response = self.client.post(self.url_hapus_berkas(self.cetak))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["pesan"], "Produk ini tidak memiliki berkas.")

    def test_hapus_produk_beserta_berkasnya(self):
        nama = self.ebook.berkas.name
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url_hapus_produk(self.ebook))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["pesan"], "Produk Ebook (PDF) untuk “Moby Dick” dihapus.")
        self.assertFalse(Produk.objects.filter(pk=self.ebook.pk).exists())
        self.assertFalse(default_storage.exists(nama))
        self.assertTrue(LogEntry.objects.filter(object_id=str(self.buku.pk)).exists())

    def test_produk_terakhir_tidak_bisa_dihapus(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url_hapus_produk(self.ebook))
        response = self.client.post(self.url_hapus_produk(self.cetak))
        self.assertEqual(response.status_code, 400)
        self.assertIn("minimal 1 produk", response.json()["pesan"])
        self.assertTrue(Produk.objects.filter(pk=self.cetak.pk).exists())

    def test_produk_yang_pernah_dipesan_tidak_bisa_dihapus(self):
        pembeli = User.objects.create_user(email="pembeli@example.com", password="x", nama_lengkap="Pembeli")
        pesanan = Pesanan.objects.create(pembeli=pembeli)
        ItemPesanan.objects.create(
            pesanan=pesanan, produk=self.ebook, judul=self.buku.judul, format=self.ebook.format, harga_satuan=40000
        )
        response = self.client.post(self.url_hapus_produk(self.ebook))
        self.assertEqual(response.status_code, 409)
        self.assertIn("sudah pernah dipesan", response.json()["pesan"])
        self.assertTrue(Produk.objects.filter(pk=self.ebook.pk).exists())
        self.assertTrue(default_storage.exists(self.ebook.berkas.name))

    def test_hanya_menerima_post(self):
        self.assertEqual(self.client.get(self.url_hapus_berkas(self.ebook)).status_code, 405)
        self.assertEqual(self.client.get(self.url_hapus_produk(self.ebook)).status_code, 405)
        self.ebook.refresh_from_db()
        self.assertTrue(self.ebook.berkas)

    def test_tanpa_masuk_dialihkan_ke_halaman_masuk(self):
        self.client.logout()
        response = self.client.post(self.url_hapus_produk(self.ebook))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(reverse("admin:login")))
        self.assertTrue(Produk.objects.filter(pk=self.ebook.pk).exists())

    def test_staf_tanpa_izin_ditolak(self):
        # Admin tanpa izin katalog (is_staff mengikuti role admin, tetapi bukan superuser).
        staf = User.objects.create_user(
            email="staf@example.com", password="x", nama_lengkap="Staf", role=User.Role.ADMIN
        )
        self.assertTrue(staf.is_staff)
        self.client.force_login(staf)
        self.assertEqual(self.client.post(self.url_hapus_berkas(self.ebook)).status_code, 403)
        self.assertEqual(self.client.post(self.url_hapus_produk(self.ebook)).status_code, 403)
        self.assertTrue(Produk.objects.filter(pk=self.ebook.pk).exists())
