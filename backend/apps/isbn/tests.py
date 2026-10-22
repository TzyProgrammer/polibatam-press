from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings

from apps.accounts.models import User
from core.testing import STORAGES_MEMORI, berkas_uji

from .models import PengajuanISBN
from .validators import validasi_isbn13


class ValidasiISBNTests(SimpleTestCase):
    def test_isbn_valid(self):
        for nilai in ("978-0-306-40615-7", "9780306406157", "978-623-000-000-3"):
            with self.subTest(nilai=nilai):
                validasi_isbn13(nilai)

    def test_isbn_tidak_valid(self):
        kasus = (
            "978-0-306-40615-8",  # digit periksa salah
            "977-1234-5678-98",   # digit periksa benar, tetapi awalan ISSN, bukan ISBN
            "978030640615",       # hanya 12 digit
            "97803064061X7",      # mengandung huruf
        )
        for nilai in kasus:
            with self.subTest(nilai=nilai), self.assertRaises(ValidationError):
                validasi_isbn13(nilai)


@override_settings(STORAGES=STORAGES_MEMORI)
class PengajuanISBNTests(TestCase):
    def setUp(self):
        pemohon = User.objects.create_user(email="penulis@example.com", password="x", nama_lengkap="Penulis")
        self.pengajuan = PengajuanISBN(
            pemohon=pemohon, judul="Naskah Uji", penulis="Penulis", sinopsis="Sinopsis singkat.",
            berkas_naskah=berkas_uji("naskah.pdf"),
        )

    def test_pengajuan_baru_menunggu_verifikasi(self):
        self.pengajuan.full_clean()
        self.pengajuan.save()
        self.assertEqual(self.pengajuan.status, PengajuanISBN.Status.MENUNGGU_VERIFIKASI)

    def test_naskah_hanya_pdf_atau_docx(self):
        self.pengajuan.berkas_naskah = berkas_uji("naskah.exe")
        with self.assertRaises(ValidationError) as ctx:
            self.pengajuan.full_clean()
        self.assertIn("berkas_naskah", ctx.exception.message_dict)

    def test_selesai_wajib_nomor_isbn_valid(self):
        self.pengajuan.status = PengajuanISBN.Status.SELESAI
        with self.assertRaises(ValidationError) as ctx:
            self.pengajuan.full_clean()
        self.assertIn("nomor_isbn", ctx.exception.message_dict)
        self.pengajuan.nomor_isbn = "978-0-306-40615-8"
        with self.assertRaises(ValidationError):
            self.pengajuan.full_clean()
        self.pengajuan.nomor_isbn = "978-0-306-40615-7"
        self.pengajuan.full_clean()

    def test_ditolak_wajib_alasan(self):
        self.pengajuan.status = PengajuanISBN.Status.DITOLAK
        with self.assertRaises(ValidationError) as ctx:
            self.pengajuan.full_clean()
        self.assertIn("alasan_penolakan", ctx.exception.message_dict)
        self.pengajuan.alasan_penolakan = "Naskah belum lengkap."
        self.pengajuan.full_clean()
