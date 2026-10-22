"""Tes Tahap D: watermark dinamis ebook, salinan per pembeli, dan lacak kebocoran (FR-13, FR-16)."""

import io
from datetime import datetime, timedelta
from io import StringIO
from unittest import mock
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfReader, PdfWriter
from pypdf.generic import RectangleObject
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import User
from apps.catalog.models import Buku, Produk
from apps.orders.models import ItemPesanan, Pesanan
from core.testing import KUNCI_INDUK_UJI, RAHASIA_UJI, STORAGES_MEMORI, PenyimpananMemoriUji, berkas_uji

from . import lacak, watermark
from .checks import periksa_rahasia_drm
from .layanan import berikan_hak_akses, siapkan_salinan_ebook
from .models import HakAkses, SalinanEbook
from .tasks import buat_salinan_ebook
from .watermark import AWALAN_KODE, GagalWatermark, IdentitasPembelian

IDENTITAS_UJI = IdentitasPembelian(
    kode="ABCD-1234-EF56-7890",
    nama="Budi Santoso",
    email_samaran="bu***@gmail.com",
    nomor_pesanan="PP-20261022-ABC123",
    tanggal="22-10-2026",
)
WAKTU_BAYAR = datetime(2026, 10, 22, 9, 30, tzinfo=ZoneInfo("Asia/Jakarta"))


def buat_pdf(jumlah_halaman=3, judul="Buku Uji", putar_halaman=None, kotak_potong=None,
             sandi_pemilik=None, sandi_pembuka=""):
    """PDF contoh berisi teks 'Isi asli halaman N' di setiap halaman."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle(judul)
    for nomor in range(1, jumlah_halaman + 1):
        c.setFont("Times-Roman", 12)
        c.drawString(72, 770, f"Isi asli halaman {nomor}")
        c.showPage()
    c.save()
    data = buffer.getvalue()
    if putar_halaman is None and kotak_potong is None and sandi_pemilik is None:
        return data
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(data)))
    if putar_halaman is not None:
        writer.pages[putar_halaman].rotate(90)
    if kotak_potong is not None:
        writer.pages[0].cropbox = RectangleObject(kotak_potong)
    if sandi_pemilik is not None:
        writer.encrypt(user_password=sandi_pembuka, owner_password=sandi_pemilik, algorithm="AES-128")
    keluaran = io.BytesIO()
    writer.write(keluaran)
    return keluaran.getvalue()


def tanpa_metadata(data):
    """Salin semua halaman ke PDF baru tanpa metadata, seperti pembocor yang menghapus metadata."""
    writer = PdfWriter()
    for halaman in PdfReader(io.BytesIO(data)).pages:
        writer.add_page(halaman)
    keluaran = io.BytesIO()
    writer.write(keluaran)
    return keluaran.getvalue()


def gabungkan(*daftar_data):
    writer = PdfWriter()
    for data in daftar_data:
        for halaman in PdfReader(io.BytesIO(data)).pages:
            writer.add_page(halaman)
    keluaran = io.BytesIO()
    writer.write(keluaran)
    return keluaran.getvalue()


def teks_halaman(data):
    return [halaman.extract_text() for halaman in PdfReader(io.BytesIO(data)).pages]


class WatermarkTests(SimpleTestCase):
    def test_samarkan_email(self):
        for email, hasil in (
            ("budi.santoso@gmail.com", "bu***@gmail.com"),
            ("ab@polibatam.ac.id", "a***@polibatam.ac.id"),
            ("a@x.id", "a***@x.id"),
        ):
            with self.subTest(email=email):
                self.assertEqual(watermark.samarkan_email(email), hasil)

    def test_setiap_halaman_bertanda_dan_isi_asli_tetap(self):
        data = buat_pdf(3, putar_halaman=2, kotak_potong=(20, 20, 575, 822))
        hasil = watermark.beri_watermark(data, IDENTITAS_UJI)
        reader = PdfReader(io.BytesIO(hasil))
        self.assertEqual(len(reader.pages), 3)
        for nomor, teks in enumerate(teks_halaman(hasil), start=1):
            with self.subTest(halaman=nomor):
                self.assertIn(f"Isi asli halaman {nomor}", teks)
                self.assertIn("Budi Santoso", teks)
                self.assertIn("bu***@gmail.com · PP-20261022-ABC123", teks)
                self.assertIn("Kode ABCD-1234-EF56-7890 · Dibeli 22-10-2026", teks)
                self.assertIn(f"{AWALAN_KODE}ABCD-1234-EF56-7890", teks)  # teks tak terlihat
        # Rotasi dipindahkan ke isi halaman agar tanda tegak sesuai tampilan.
        self.assertEqual(reader.pages[2].rotation, 0)
        metadata = reader.metadata
        self.assertEqual(metadata[watermark.META_KODE], "ABCD-1234-EF56-7890")
        self.assertEqual(metadata[watermark.META_PESANAN], "PP-20261022-ABC123")
        self.assertEqual(metadata["/Title"], "Buku Uji")  # metadata asli dipertahankan
        # PDF asli tidak berubah.
        self.assertNotIn("Budi Santoso", "".join(teks_halaman(data)))

    def test_kode_terbaca_dari_metadata_dan_teks(self):
        hasil = watermark.beri_watermark(buat_pdf(3), IDENTITAS_UJI)
        terbaca = watermark.baca_kode(hasil)
        self.assertEqual(terbaca.kode_metadata, "ABCD-1234-EF56-7890")
        self.assertEqual(terbaca.kode_teks, ("ABCD-1234-EF56-7890",))
        self.assertEqual((terbaca.halaman_diperiksa, terbaca.jumlah_halaman), (3, 3))
        self.assertEqual(watermark.baca_kode(hasil, maks_halaman=1).halaman_diperiksa, 1)
        watermark.verifikasi_watermark(hasil, IDENTITAS_UJI)

    def test_kode_tetap_terbaca_setelah_metadata_dihapus(self):
        hasil = tanpa_metadata(watermark.beri_watermark(buat_pdf(2), IDENTITAS_UJI))
        terbaca = watermark.baca_kode(hasil)
        self.assertIsNone(terbaca.kode_metadata)
        self.assertEqual(terbaca.kode_teks, ("ABCD-1234-EF56-7890",))

    def test_deret_heksadesimal_lain_di_isi_buku_tidak_dianggap_kode(self):
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        c.drawString(72, 770, "Alamat memori 0000-1111-2222-3333 bukan kode watermark")
        c.save()
        self.assertEqual(watermark.baca_kode(buffer.getvalue()).kode_teks, ())

    def test_nama_dengan_karakter_di_luar_latin(self):
        identitas = IdentitasPembelian("ABCD-1234-EF56-7890", "Siti 🙂 Ñandú", "si***@x.id", "PP-1", "22-10-2026")
        teks = teks_halaman(watermark.beri_watermark(buat_pdf(1), identitas))[0]
        self.assertIn("Siti ? Ñandú", teks)

    def test_pdf_berkata_sandi_pemilik_tetap_bisa_diproses(self):
        data = buat_pdf(2, sandi_pemilik="rahasia-pemilik")
        self.assertTrue(PdfReader(io.BytesIO(data)).is_encrypted)
        hasil = watermark.beri_watermark(data, IDENTITAS_UJI)
        self.assertFalse(PdfReader(io.BytesIO(hasil)).is_encrypted)
        watermark.verifikasi_watermark(hasil, IDENTITAS_UJI)

    def test_pdf_tidak_valid_ditolak_dengan_pesan_jelas(self):
        for data, pesan in (
            (b"ini bukan pdf", "Berkas bukan PDF."),
            (buat_pdf(1, sandi_pemilik="pemilik", sandi_pembuka="pembuka"), "PDF terkunci kata sandi"),
        ):
            with self.subTest(pesan=pesan), self.assertRaisesMessage(GagalWatermark, pesan):
                watermark.beri_watermark(data, IDENTITAS_UJI)
        # pypdf mencatat peringatan untuk PDF rusak sebelum gagal.
        with self.assertLogs("pypdf", level="WARNING"):
            with self.assertRaisesMessage(GagalWatermark, "PDF tidak dapat dibaca"):
                watermark.beri_watermark(b"%PDF-1.4\nrusak", IDENTITAS_UJI)

    def test_verifikasi_gagal_untuk_pdf_tanpa_watermark(self):
        with self.assertRaises(GagalWatermark):
            watermark.verifikasi_watermark(buat_pdf(1), IDENTITAS_UJI)


class EbookTestCase(TestCase):
    """Data bersama: pembeli dengan pesanan lunas berisi satu ebook."""

    def setUp(self):
        cache.clear()
        self.pembeli = User.objects.create_user(
            email="budi.santoso@example.com", password="x", nama_lengkap="Budi Santoso"
        )
        buku = Buku.objects.create(judul="Pengantar Keamanan Data", penulis="Penulis")
        self.pdf_asli = buat_pdf(2)
        self.ebook = Produk.objects.create(
            buku=buku, format=Produk.Format.EBOOK, harga=40000, berkas=ContentFile(self.pdf_asli, name="asli.pdf")
        )
        self.item = self.buat_item(self.pembeli)

    def buat_item(self, pembeli, produk=None):
        produk = produk or self.ebook
        pesanan = Pesanan.objects.create(
            pembeli=pembeli, status_pembayaran=Pesanan.StatusPembayaran.LUNAS, dibayar_pada=WAKTU_BAYAR
        )
        return ItemPesanan.objects.create(
            pesanan=pesanan, produk=produk, judul=produk.buku.judul, format=produk.format, harga_satuan=produk.harga
        )

    def beri_akses(self, item=None):
        with mock.patch.object(buat_salinan_ebook, "delay") as delay, self.captureOnCommitCallbacks(execute=True):
            hak = berikan_hak_akses(item or self.item)
        return hak, delay

    def salinan_siap(self, item=None):
        hak, _ = self.beri_akses(item)
        self.assertEqual(buat_salinan_ebook(hak.salinan_ebook.pk), "siap")
        hak.salinan_ebook.refresh_from_db()
        return hak.salinan_ebook

    def isi_salinan(self, salinan):
        with default_storage.open(salinan.berkas.name, "rb") as berkas:
            return berkas.read()


@override_settings(STORAGES=STORAGES_MEMORI, WATERMARK_SECRET=RAHASIA_UJI, FERNET_MASTER_KEY=KUNCI_INDUK_UJI)
class SalinanEbookTests(EbookTestCase):
    def test_hak_akses_ebook_menyiapkan_salinan_sekali(self):
        hak, delay = self.beri_akses()
        salinan = SalinanEbook.objects.get(hak_akses=hak)
        self.assertEqual(salinan.status, SalinanEbook.Status.MENUNGGU)
        delay.assert_called_once_with(salinan.pk)
        hak_lagi, delay = self.beri_akses()  # dipanggil ulang: tidak membuat apa pun lagi
        self.assertEqual(hak_lagi, hak)
        delay.assert_not_called()
        self.assertEqual(SalinanEbook.objects.count(), 1)

    def test_hak_akses_produk_lain(self):
        audiobook = Produk.objects.create(
            buku=self.ebook.buku, format=Produk.Format.AUDIOBOOK, harga=60000, berkas=berkas_uji("a.mp3")
        )
        cetak = Produk.objects.create(buku=self.ebook.buku, format=Produk.Format.CETAK, harga=75000, stok=3)
        hak, delay = self.beri_akses(self.buat_item(self.pembeli, audiobook))
        self.assertEqual(hak.produk, audiobook)
        delay.assert_not_called()
        self.assertIsNone(berikan_hak_akses(self.buat_item(self.pembeli, cetak)))
        self.assertFalse(SalinanEbook.objects.exists())

    def test_task_membuat_salinan_ber_watermark(self):
        salinan = self.salinan_siap()
        self.assertEqual(salinan.status, SalinanEbook.Status.SIAP)
        self.assertIsNotNone(salinan.siap_pada)
        self.assertRegex(salinan.berkas.name, r"^salinan/ebook/[0-9a-f]{32}\.pdf$")
        isi = self.isi_salinan(salinan)
        terbaca = watermark.baca_kode(isi)
        self.assertEqual(terbaca.kode_metadata, salinan.kode_watermark)
        teks = teks_halaman(isi)[0]
        nomor = self.item.pesanan.nomor
        self.assertIn("Budi Santoso", teks)
        self.assertIn(f"bu***@example.com · {nomor}", teks)
        self.assertIn(f"Kode {salinan.kode_watermark} · Dibeli 22-10-2026", teks)
        # Berkas asli produk tetap tanpa watermark.
        with default_storage.open(self.ebook.berkas.name, "rb") as berkas:
            self.assertEqual(berkas.read(), self.pdf_asli)

    def test_proses_ulang_mengganti_berkas_lama(self):
        salinan = self.salinan_siap()
        lama = salinan.berkas.name
        with mock.patch.object(buat_salinan_ebook, "delay") as delay, self.captureOnCommitCallbacks(execute=True):
            siapkan_salinan_ebook(salinan.hak_akses, paksa=True)
        delay.assert_called_once_with(salinan.pk)
        self.assertEqual(buat_salinan_ebook(salinan.pk), "siap")
        salinan.refresh_from_db()
        self.assertNotEqual(salinan.berkas.name, lama)
        self.assertFalse(default_storage.exists(lama))
        self.assertTrue(default_storage.exists(salinan.berkas.name))

    def test_pdf_asli_rusak_membuat_status_gagal(self):
        rusak = default_storage.save("asli/ebook/rusak.pdf", ContentFile(b"bukan pdf"))
        Produk.objects.filter(pk=self.ebook.pk).update(berkas=rusak)
        hak, _ = self.beri_akses()
        with self.assertLogs("apps.drm.tasks", level="ERROR"):
            self.assertEqual(buat_salinan_ebook(hak.salinan_ebook.pk), "gagal")
        salinan = SalinanEbook.objects.get()
        self.assertEqual(salinan.status, SalinanEbook.Status.GAGAL)
        self.assertEqual(salinan.pesan_galat, "Berkas bukan PDF.")
        self.assertFalse(salinan.berkas)

    def test_hapus_hak_akses_ikut_menghapus_pdf_salinan(self):
        salinan = self.salinan_siap()
        nama = salinan.berkas.name
        with self.captureOnCommitCallbacks(execute=True):
            salinan.hak_akses.delete()
        self.assertFalse(SalinanEbook.objects.exists())
        self.assertFalse(default_storage.exists(nama))

    def test_task_untuk_salinan_yang_sudah_dihapus(self):
        self.assertEqual(buat_salinan_ebook(999999), "hilang")


@override_settings(STORAGES=STORAGES_MEMORI, WATERMARK_SECRET=RAHASIA_UJI, FERNET_MASTER_KEY=KUNCI_INDUK_UJI)
class ApiEbookTests(EbookTestCase, APITestCase):
    def setUp(self):
        super().setUp()
        self.lain = User.objects.create_user(email="lain@example.com", password="x", nama_lengkap="Lain")

    def login(self, pengguna):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(pengguna)}")

    def url(self, produk=None):
        return reverse("drm-ebook", args=[(produk or self.ebook).pk])

    def test_pemilik_mendapat_presigned_url_lima_menit(self):
        salinan = self.salinan_siap()
        self.login(self.pembeli)
        sebelum = timezone.now()
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(
            response.data["url"],
            f"{PenyimpananMemoriUji.BASIS_URL}{salinan.berkas.name}?X-Amz-Expires=300&X-Amz-Signature=uji",
        )
        self.assertNotIn(self.ebook.berkas.name, response.data["url"])  # bukan berkas asli
        self.assertTrue(sebelum + timedelta(seconds=300) <= response.data["kedaluwarsa"])

    def test_salinan_belum_siap_atau_gagal(self):
        hak, _ = self.beri_akses()
        self.login(self.pembeli)
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["status"], "menunggu")
        SalinanEbook.objects.filter(hak_akses=hak).update(status=SalinanEbook.Status.GAGAL)
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["detail"], "Salinan ebook gagal disiapkan. Hubungi admin.")

    def test_salinan_yang_belum_pernah_dibuat_disiapkan_saat_dibuka(self):
        HakAkses.objects.create(pembeli=self.pembeli, produk=self.ebook, item_pesanan=self.item)
        self.login(self.pembeli)
        with mock.patch.object(buat_salinan_ebook, "delay") as delay, self.captureOnCommitCallbacks(execute=True):
            response = self.client.get(self.url())
        self.assertEqual(response.status_code, 409)
        delay.assert_called_once_with(SalinanEbook.objects.get().pk)

    def test_penolakan(self):
        self.salinan_siap()
        audiobook = Produk.objects.create(
            buku=self.ebook.buku, format=Produk.Format.AUDIOBOOK, harga=60000, berkas=berkas_uji("a.mp3")
        )
        self.assertEqual(self.client.get(self.url()).status_code, 401)
        self.login(self.lain)
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["detail"], "Anda tidak memiliki hak akses ke ebook ini.")
        self.login(self.pembeli)
        self.assertEqual(self.client.get(self.url(audiobook)).status_code, 404)
        self.assertEqual(self.client.get(reverse("drm-ebook", args=[999999])).status_code, 404)
        HakAkses.objects.filter(pembeli=self.pembeli).update(aktif=False)
        self.assertEqual(self.client.get(self.url()).status_code, 403)


@override_settings(STORAGES=STORAGES_MEMORI, WATERMARK_SECRET=RAHASIA_UJI, FERNET_MASTER_KEY=KUNCI_INDUK_UJI)
class LacakKebocoranTests(EbookTestCase):
    def setUp(self):
        super().setUp()
        self.salinan = self.salinan_siap()
        self.pdf_bocor = self.isi_salinan(self.salinan)

    def identitas_palsu(self, kode="0000-1111-2222-3333"):
        return IdentitasPembelian(kode, "Orang Lain", "or***@x.id", "PP-PALSU", "01-01-2026")

    def test_pdf_bocor_menunjuk_pembeli(self):
        hasil = lacak.lacak_kebocoran(self.pdf_bocor)
        self.assertEqual(len(hasil.temuan), 1)
        temuan = hasil.temuan[0]
        self.assertEqual(temuan.status, lacak.ASLI)
        self.assertEqual(temuan.sumber, ["metadata", "teks halaman"])
        self.assertEqual(temuan.salinan, self.salinan)
        self.assertEqual(temuan.salinan.hak_akses.pembeli, self.pembeli)
        self.assertEqual(hasil.catatan, [])

    def test_metadata_dihapus(self):
        hasil = lacak.lacak_kebocoran(tanpa_metadata(self.pdf_bocor))
        self.assertEqual([(t.status, t.sumber) for t in hasil.temuan], [(lacak.ASLI, ["teks halaman"])])
        self.assertIn("Metadata kode tidak ada", hasil.catatan[0])

    def test_kode_palsu_tidak_terdaftar(self):
        pdf = watermark.beri_watermark(buat_pdf(1), self.identitas_palsu())
        temuan = lacak.lacak_kebocoran(pdf).temuan
        self.assertEqual([t.status for t in temuan], [lacak.TIDAK_TERDAFTAR])
        self.assertIsNone(temuan[0].salinan)

    def test_kode_terdaftar_tetapi_hmac_tidak_cocok(self):
        # Basis data diubah langsung agar kode palsu seolah milik salinan ini.
        SalinanEbook.objects.filter(pk=self.salinan.pk).update(kode_watermark="0000-1111-2222-3333")
        pdf = watermark.beri_watermark(buat_pdf(1), self.identitas_palsu())
        temuan = lacak.lacak_kebocoran(pdf).temuan
        self.assertEqual([t.status for t in temuan], [lacak.TIDAK_SAH])
        self.assertEqual(temuan[0].salinan, self.salinan)

    def test_gabungan_dua_salinan(self):
        siti = User.objects.create_user(email="siti@example.com", password="x", nama_lengkap="Siti")
        salinan_siti = self.salinan_siap(self.buat_item(siti))
        hasil = lacak.lacak_kebocoran(gabungkan(self.pdf_bocor, self.isi_salinan(salinan_siti)))
        self.assertEqual({t.salinan for t in hasil.temuan_asli}, {self.salinan, salinan_siti})
        self.assertTrue(any("lebih dari satu kode asli" in c for c in hasil.catatan))

    def test_pdf_tanpa_kode_atau_metadata_bukan_kode(self):
        self.assertEqual(lacak.lacak_kebocoran(buat_pdf(1)).temuan, [])
        writer = PdfWriter(clone_from=PdfReader(io.BytesIO(buat_pdf(1))))
        writer.add_metadata({watermark.META_KODE: "bukan-kode"})
        keluaran = io.BytesIO()
        writer.write(keluaran)
        temuan = lacak.lacak_kebocoran(keluaran.getvalue()).temuan
        self.assertEqual([(t.kode, t.status) for t in temuan], [("bukan-kode", lacak.FORMAT_SALAH)])


@override_settings(STORAGES=STORAGES_MEMORI, WATERMARK_SECRET=RAHASIA_UJI, FERNET_MASTER_KEY=KUNCI_INDUK_UJI)
class AdminSalinanEbookTests(EbookTestCase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser(email="admin@example.com", password="x", nama_lengkap="Admin")
        self.client.force_login(self.admin)
        self.salinan = self.salinan_siap()
        self.url_lacak = reverse("admin:drm_lacak_kebocoran")

    def unggah(self, data, nama="bocor.pdf"):
        return self.client.post(self.url_lacak, {"berkas": SimpleUploadedFile(nama, data, "application/pdf")})

    def test_halaman_lacak_menemukan_pembeli(self):
        self.assertContains(self.client.get(reverse("admin:drm_salinanebook_changelist")), self.url_lacak)
        self.assertEqual(self.client.get(self.url_lacak).status_code, 200)
        response = self.unggah(self.isi_salinan(self.salinan))
        self.assertContains(response, "Sumber kebocoran")
        self.assertContains(response, "budi.santoso@example.com")
        self.assertContains(response, self.item.pesanan.nomor)
        self.assertContains(response, self.salinan.kode_watermark)
        self.assertContains(response, "Asli: kode diterbitkan sistem")

    def test_lacak_kebocoran_tampil_di_menu_admin(self):
        self.assertEqual(self.url_lacak, "/admin/drm/lacak-kebocoran/")
        tautan = f'<a href="{self.url_lacak}">Lacak kebocoran</a>'
        for halaman in (reverse("admin:index"), reverse("admin:app_list", args=["drm"])):
            with self.subTest(halaman=halaman):
                self.assertContains(self.client.get(halaman), tautan, html=True)
        # Di halaman lacak, hanya menu Lacak kebocoran yang ditandai sebagai halaman aktif.
        response = self.client.get(self.url_lacak)
        self.assertContains(response, 'class="model-lacakkebocoran current-model"')
        self.assertNotContains(response, 'class="model-salinanebook current-model"')

    def test_staf_tanpa_izin_tidak_melihat_menu_dan_ditolak(self):
        staf = User.objects.create_user(email="staf@example.com", password="x", nama_lengkap="Staf", role="admin")
        self.client.force_login(staf)
        self.assertNotContains(self.client.get(reverse("admin:index")), "Lacak kebocoran")
        self.assertEqual(self.client.get(self.url_lacak).status_code, 403)

    def test_halaman_lacak_menolak_bukan_pdf_dan_tanpa_login_admin(self):
        self.assertContains(self.unggah(b"bukan pdf", "catatan.txt"), "Berkas bukan PDF.")
        self.client.logout()
        response = self.client.get(self.url_lacak)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("admin:login"), response["Location"])

    def test_salinan_hanya_bisa_dilihat_dan_bisa_diproses_ulang(self):
        response = self.client.get(reverse("admin:drm_salinanebook_change", args=[self.salinan.pk]))
        self.assertNotContains(response, 'name="_save"')
        self.assertContains(response, 'class="closelink"')
        with mock.patch.object(buat_salinan_ebook, "delay") as delay, self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("admin:drm_salinanebook_changelist"),
                {"action": "proses_ulang", "_selected_action": [self.salinan.pk]},
            )
        self.assertEqual(response.status_code, 302)
        delay.assert_called_once_with(self.salinan.pk)


@override_settings(STORAGES=STORAGES_MEMORI, WATERMARK_SECRET=RAHASIA_UJI, FERNET_MASTER_KEY=KUNCI_INDUK_UJI)
class BuatAksesUjiEbookTests(EbookTestCase):
    @override_settings(DEBUG=True)
    def test_hak_akses_ebook_beserta_salinan(self):
        keluaran = StringIO()
        argumen = ("--email", self.pembeli.email, "--produk", str(self.ebook.pk))
        with mock.patch.object(buat_salinan_ebook, "delay") as delay, self.captureOnCommitCallbacks(execute=True):
            call_command("buat_akses_uji", *argumen, stdout=keluaran)
        salinan = SalinanEbook.objects.get(hak_akses__pembeli=self.pembeli)
        delay.assert_called_once_with(salinan.pk)
        self.assertEqual(salinan.hak_akses.item_pesanan.pesanan.midtrans_payment_type, "uji-lokal")
        self.assertIn(f"kode {salinan.kode_watermark}", keluaran.getvalue())
        self.assertIn(f"/uji-pemutar/?ebook={self.ebook.pk}", keluaran.getvalue())


class PemeriksaanRahasiaTests(SimpleTestCase):
    def test_peringatan_bila_rahasia_kosong(self):
        with self.settings(FERNET_MASTER_KEY="", WATERMARK_SECRET=""):
            self.assertEqual([p.id for p in periksa_rahasia_drm(None)], ["drm.W001", "drm.W002"])
        with self.settings(FERNET_MASTER_KEY=KUNCI_INDUK_UJI, WATERMARK_SECRET=RAHASIA_UJI):
            self.assertEqual(periksa_rahasia_drm(None), [])
