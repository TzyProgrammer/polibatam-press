"""Tes Tahap G: pengajuan ISBN oleh pemohon (FR-14, FR-15) dan verifikasi admin."""

import io
import zipfile
from unittest import mock

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import User
from apps.notifications.models import Notifikasi
from core.testing import STORAGES_MEMORI, berkas_uji

from .models import PengajuanISBN

PDF = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n"
ISBN_VALID = "978-602-8519-93-9"


def isi_docx(lengkap=True):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as arsip:
        arsip.writestr("[Content_Types].xml", "<Types/>")
        if lengkap:
            arsip.writestr("word/document.xml", "<w:document/>")
    return buffer.getvalue()


def naskah(nama="naskah.pdf", isi=PDF):
    return SimpleUploadedFile(nama, isi, content_type="application/octet-stream")


@override_settings(STORAGES=STORAGES_MEMORI)
class PengajuanTestCase(APITestCase):
    def setUp(self):
        cache.clear()
        self.pemohon = User.objects.create_user(email="penulis@example.com", password="x", nama_lengkap="Penulis")
        self.login(self.pemohon)

    def login(self, pengguna):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(pengguna)}")

    def ajukan(self, kode=201, **ubahan):
        data = {
            "judul": "Pemrograman Web Aman",
            "penulis": "Siti Aminah; Budi Santoso",
            "sinopsis": "Panduan membangun aplikasi web yang aman.",
            "jumlah_halaman": 180,
            "berkas_naskah": naskah(),
        }
        data.update(ubahan)
        data = {k: v for k, v in data.items() if v is not None}
        response = self.client.post(reverse("isbn-pengajuan"), data, format="multipart")
        self.assertEqual(response.status_code, kode, response.data)
        return response

    def buat(self, pemohon=None, **lain):
        lain.setdefault("berkas_naskah", berkas_uji("naskah.pdf", PDF))
        return PengajuanISBN.objects.create(
            pemohon=pemohon or self.pemohon, judul=lain.pop("judul", "Naskah Lama"), penulis="Penulis",
            sinopsis="Sinopsis.", **lain,
        )


class AjukanTests(PengajuanTestCase):
    def test_ajukan_pdf(self):
        data = self.ajukan().data
        pengajuan = PengajuanISBN.objects.get()
        self.assertEqual((pengajuan.pemohon, pengajuan.status), (self.pemohon, "menunggu_verifikasi"))
        self.assertRegex(pengajuan.berkas_naskah.name, r"^isbn/naskah/[0-9a-f]{32}\.pdf$")  # nama asli tidak dipakai
        self.assertEqual((data["status"], data["status_label"]), ("menunggu_verifikasi", "Menunggu verifikasi"))
        self.assertEqual(data["naskah"]["nama"], "naskah-pemrograman-web-aman.pdf")
        self.assertIn("X-Amz-Expires=300", data["naskah"]["url"])
        self.assertNotIn("catatan_admin", data)
        notifikasi = Notifikasi.objects.get(penerima=self.pemohon)
        self.assertEqual((notifikasi.kategori, notifikasi.judul), ("isbn", "Pengajuan ISBN diterima"))
        self.assertEqual(notifikasi.tautan, f"/isbn/{pengajuan.pk}")

    def test_ajukan_docx(self):
        data = self.ajukan(berkas_naskah=naskah("Naskah Final.DOCX", isi_docx()), jumlah_halaman=None).data
        self.assertEqual(data["naskah"]["format"], "docx")
        self.assertIsNone(data["jumlah_halaman"])

    def test_isian_wajib(self):
        response = self.ajukan(kode=400, judul="", sinopsis="", berkas_naskah=None, jumlah_halaman=0)
        self.assertEqual(set(response.data), {"judul", "sinopsis", "berkas_naskah", "jumlah_halaman"})
        self.assertFalse(PengajuanISBN.objects.exists())

    def test_berkas_harus_benar_benar_pdf_atau_docx(self):
        kasus = [
            (naskah("naskah.exe", b"MZ..."), "pdf, docx"),  # ekstensi
            (naskah("naskah.pdf", b"bukan pdf, hanya diganti namanya"), "bukan PDF"),
            (naskah("naskah.docx", PDF), "bukan dokumen Word"),
            (naskah("naskah.docx", isi_docx(lengkap=False)), "bukan dokumen Word"),  # ZIP biasa, bukan DOCX
        ]
        for berkas, pesan in kasus:
            with self.subTest(nama=berkas.name):
                response = self.ajukan(kode=400, berkas_naskah=berkas)
                self.assertIn(pesan, str(response.data["berkas_naskah"]))
        self.assertFalse(PengajuanISBN.objects.exists())

    def test_ukuran_maksimal(self):
        with mock.patch("apps.isbn.validators.UKURAN_MAKS_NASKAH_MB", 0.00001):  # ±10 byte
            response = self.ajukan(kode=400)
        self.assertIn("Ukuran naskah maksimal", str(response.data["berkas_naskah"]))

    def test_batas_pengajuan_yang_belum_selesai(self):
        aktif = [self.buat(judul=f"Naskah {n}") for n in range(5)]
        response = self.ajukan(kode=400)
        self.assertIn("5 pengajuan yang belum selesai", str(response.data))
        PengajuanISBN.objects.filter(pk=aktif[0].pk).update(status="ditolak", alasan_penolakan="Belum lengkap.")
        self.ajukan()

    def test_unggah_dibatasi_20_per_jam(self):
        for _ in range(20):
            self.ajukan(kode=400, judul="")
        self.assertEqual(self.ajukan(kode=429).data["detail"][:26], "Terlalu banyak permintaan.")
        self.assertEqual(self.client.get(reverse("isbn-pengajuan")).status_code, 200)  # melihat daftar tidak dibatasi

    def test_perlu_login_dan_hanya_multipart(self):
        self.assertEqual(self.client.post(reverse("isbn-pengajuan"), {"judul": "x"}, format="json").status_code, 415)
        self.client.credentials()
        self.assertEqual(self.client.get(reverse("isbn-pengajuan")).status_code, 401)


class LihatPengajuanTests(PengajuanTestCase):
    def test_daftar_dan_detail_hanya_milik_sendiri(self):
        milik = self.buat(judul="Milik Saya")
        lain = User.objects.create_user(email="lain@example.com", password="x", nama_lengkap="Lain")
        punya_lain = self.buat(pemohon=lain, judul="Milik Orang Lain")
        daftar = self.client.get(reverse("isbn-pengajuan")).data
        self.assertEqual([p["judul"] for p in daftar["results"]], ["Milik Saya"])
        self.assertEqual(self.client.get(reverse("isbn-pengajuan-detail", args=[milik.pk])).status_code, 200)
        response = self.client.get(reverse("isbn-pengajuan-detail", args=[punya_lain.pk]))
        self.assertEqual((response.status_code, response.data["detail"]), (404, "Pengajuan tidak ditemukan."))

    def test_nomor_isbn_dan_alasan_hanya_tampil_pada_status_yang_sesuai(self):
        diproses = self.buat(status="diproses", nomor_isbn=ISBN_VALID, catatan_admin="Internal saja")
        selesai = self.buat(status="selesai", nomor_isbn=ISBN_VALID, tanggal_penetapan=timezone.localdate())
        ditolak = self.buat(status="ditolak", alasan_penolakan="Naskah belum lengkap.")
        hasil = {p["id"]: p for p in self.client.get(reverse("isbn-pengajuan")).data["results"]}
        self.assertEqual(hasil[diproses.pk]["nomor_isbn"], "")
        self.assertEqual(hasil[selesai.pk]["nomor_isbn"], ISBN_VALID)
        self.assertEqual(hasil[ditolak.pk]["alasan_penolakan"], "Naskah belum lengkap.")
        self.assertEqual(hasil[diproses.pk]["alasan_penolakan"], "")
        detail = self.client.get(reverse("isbn-pengajuan-detail", args=[diproses.pk])).data
        self.assertNotIn("Internal saja", str(detail))


class AdminPengajuanTests(PengajuanTestCase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser(email="admin@example.com", password="x", nama_lengkap="Admin")
        self.client.force_login(self.admin)
        self.pengajuan = self.buat(judul="Pemrograman Web Aman")

    def url(self):
        return reverse("admin:isbn_pengajuanisbn_change", args=[self.pengajuan.pk])

    def simpan(self, **isian):
        data = {"status": self.pengajuan.status, "nomor_isbn": "", "tanggal_penetapan": "",
                "alasan_penolakan": "", "catatan_admin": ""}
        data.update(isian)
        response = self.client.post(self.url(), data)
        self.pengajuan.refresh_from_db()
        return response

    def pilihan(self):
        return list(self.client.get(self.url()).context["adminform"].form.fields["status"].choices)

    def notifikasi(self):
        return list(Notifikasi.objects.filter(penerima=self.pemohon).values_list("judul", "pesan"))

    def test_alur_status_sampai_isbn_terbit(self):
        # Pengajuan baru hanya bisa dilanjutkan ke Diproses (revisi Tahap R).
        self.assertEqual([v for v, _ in self.pilihan()], ["menunggu_verifikasi", "diproses"])
        self.assertEqual(self.simpan(status="diproses").status_code, 302)
        self.assertEqual([v for v, _ in self.pilihan()], ["diproses", "selesai", "ditolak"])

        gagal = self.simpan(status="selesai", nomor_isbn="978-602-8519-93-0")  # digit periksa salah
        self.assertEqual(gagal.status_code, 200)
        self.assertIn("nomor_isbn", gagal.context["adminform"].form.errors)
        self.assertEqual(self.pengajuan.status, "diproses")

        self.simpan(status="selesai", nomor_isbn=ISBN_VALID)
        self.assertEqual(self.pengajuan.status, "selesai")
        self.assertEqual(self.pengajuan.tanggal_penetapan, timezone.localdate())  # diisi otomatis
        self.assertEqual([v for v, _ in self.pilihan()], ["selesai"])  # status akhir
        self.assertEqual(
            self.notifikasi(),
            [
                ("ISBN sudah terbit", f"Nomor ISBN untuk naskah \"Pemrograman Web Aman\": {ISBN_VALID}."),
                ("Pengajuan ISBN diproses",
                 "Naskah \"Pemrograman Web Aman\" sedang diproses: diverifikasi admin lalu diajukan ke Perpusnas."),
            ],
        )
        self.assertEqual(Notifikasi.objects.filter(penerima=self.pemohon).first().tautan, f"/isbn/{self.pengajuan.pk}")

    def test_ditolak_wajib_alasan(self):
        self.simpan(status="diproses")
        gagal = self.simpan(status="ditolak")
        self.assertIn("alasan_penolakan", gagal.context["adminform"].form.errors)
        self.simpan(status="ditolak", alasan_penolakan="Naskah belum menyertakan daftar pustaka.")
        self.assertEqual(self.pengajuan.status, "ditolak")
        self.assertEqual([v for v, _ in self.pilihan()], ["ditolak"])  # status akhir
        self.assertEqual(
            self.notifikasi()[0],
            ("Pengajuan ISBN ditolak", "Pengajuan untuk naskah \"Pemrograman Web Aman\" ditolak. "
             "Alasan: Naskah belum menyertakan daftar pustaka."),
        )

    def test_status_tidak_bisa_melompat_atau_mundur(self):
        loncat = self.simpan(status="selesai", nomor_isbn=ISBN_VALID)  # belum diproses
        self.assertIn("status", loncat.context["adminform"].form.errors)
        self.assertEqual(self.pengajuan.status, "menunggu_verifikasi")

    def test_pengajuan_baru_tidak_bisa_langsung_ditolak(self):
        langsung = self.simpan(status="ditolak", alasan_penolakan="Naskah tidak lengkap.")
        self.assertEqual(langsung.status_code, 200)
        self.assertIn("status", langsung.context["adminform"].form.errors)
        self.assertEqual(self.pengajuan.status, "menunggu_verifikasi")
        self.assertEqual(self.notifikasi(), [])

    def test_selesai_mengunci_alasan_penolakan(self):
        self.simpan(status="diproses")
        self.simpan(status="selesai", nomor_isbn=ISBN_VALID, alasan_penolakan="Tidak seharusnya tersimpan.")
        self.assertEqual(self.pengajuan.status, "selesai")
        self.assertEqual(self.pengajuan.nomor_isbn, ISBN_VALID)
        self.assertEqual(self.pengajuan.alasan_penolakan, "")

    def test_ditolak_mengunci_nomor_isbn_dan_tanggal_penetapan(self):
        self.simpan(status="diproses")
        response = self.simpan(
            status="ditolak", alasan_penolakan="Naskah plagiat.", nomor_isbn="978-602-8519-93-0",  # tidak valid
            tanggal_penetapan="2026-10-26",
        )
        self.assertEqual(response.status_code, 302)  # isian kolom terkunci diabaikan, termasuk yang tidak valid
        self.assertEqual(self.pengajuan.status, "ditolak")
        self.assertEqual(self.pengajuan.nomor_isbn, "")
        self.assertIsNone(self.pengajuan.tanggal_penetapan)
        self.assertEqual(self.pengajuan.alasan_penolakan, "Naskah plagiat.")

    def test_diproses_mengunci_nomor_dan_alasan(self):
        self.simpan(status="diproses", nomor_isbn=ISBN_VALID, alasan_penolakan="Belum diputuskan.")
        self.assertEqual(self.pengajuan.status, "diproses")
        self.assertEqual(self.pengajuan.nomor_isbn, "")
        self.assertEqual(self.pengajuan.alasan_penolakan, "")

    def test_halaman_memuat_pengunci_kolom(self):
        halaman = self.client.get(self.url())
        self.assertContains(halaman, "polibatam/admin-isbn.js")
        form = halaman.context["adminform"].form
        self.assertEqual(form.fields["nomor_isbn"].widget.attrs["data-status-berlaku"], "selesai")
        self.assertEqual(form.fields["tanggal_penetapan"].widget.attrs["data-status-berlaku"], "selesai")
        self.assertEqual(form.fields["alasan_penolakan"].widget.attrs["data-status-berlaku"], "ditolak")
        self.assertContains(halaman, 'data-status-berlaku="ditolak"')

    def test_tanpa_perubahan_status_tidak_ada_notifikasi(self):
        self.simpan(catatan_admin="Sudah dicek bagian redaksi.")
        self.assertEqual(self.pengajuan.catatan_admin, "Sudah dicek bagian redaksi.")
        self.assertEqual(self.notifikasi(), [])

    def test_admin_melihat_naskah_tetapi_tidak_bisa_menambah(self):
        halaman = self.client.get(self.url())
        self.assertContains(halaman, "http://s3-uji.invalid/polibatam-press/isbn/naskah/")
        self.assertEqual(self.client.get(reverse("admin:isbn_pengajuanisbn_add")).status_code, 403)
