"""Tes Tahap G: API notifikasi di dalam aplikasi."""

from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import User

from . import layanan
from .models import Notifikasi


class NotifikasiAPITests(APITestCase):
    def setUp(self):
        self.pengguna = User.objects.create_user(email="pembeli@example.com", password="x", nama_lengkap="Pembeli")
        self.lain = User.objects.create_user(email="lain@example.com", password="x", nama_lengkap="Lain")
        self.lama = layanan.kirim(self.pengguna, Notifikasi.Kategori.PESANAN, "Lama", "Pesan lama", "/pesanan/PP-1")
        self.baru = layanan.kirim(self.pengguna, Notifikasi.Kategori.ISBN, "Baru", "Pesan baru", "/isbn/1")
        self.milik_lain = layanan.kirim(self.lain, Notifikasi.Kategori.SISTEM, "Rahasia", "Milik orang lain")
        self.login(self.pengguna)

    def login(self, pengguna):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(pengguna)}")

    def test_daftar_milik_sendiri_terbaru_dulu_dengan_jumlah_belum_dibaca(self):
        response = self.client.get(reverse("notifikasi"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(response.data["belum_dibaca"], 2)
        self.assertEqual([n["judul"] for n in response.data["results"]], ["Baru", "Lama"])
        self.assertEqual(
            response.data["results"][0],
            {
                "id": self.baru.pk, "kategori": "isbn", "kategori_label": "ISBN", "judul": "Baru",
                "pesan": "Pesan baru", "tautan": "/isbn/1", "dibaca": False,
                "dibuat": response.data["results"][0]["dibuat"],
            },
        )

    def test_tandai_satu_dibaca(self):
        response = self.client.post(reverse("notifikasi-baca", args=[self.lama.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["dibaca"])
        data = self.client.get(reverse("notifikasi")).data
        self.assertEqual(data["belum_dibaca"], 1)
        hanya_belum = self.client.get(reverse("notifikasi"), {"belum_dibaca": "1"}).data
        self.assertEqual([n["judul"] for n in hanya_belum["results"]], ["Baru"])
        # Dipanggil lagi tetap aman.
        self.assertEqual(self.client.post(reverse("notifikasi-baca", args=[self.lama.pk])).status_code, 200)

    def test_notifikasi_orang_lain_tidak_bisa_disentuh(self):
        response = self.client.post(reverse("notifikasi-baca", args=[self.milik_lain.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], "Notifikasi tidak ditemukan.")
        self.milik_lain.refresh_from_db()
        self.assertFalse(self.milik_lain.dibaca)

    def test_tandai_semua_dibaca_hanya_milik_sendiri(self):
        response = self.client.post(reverse("notifikasi-baca-semua"))
        self.assertEqual(response.data, {"ditandai": 2, "belum_dibaca": 0})
        self.assertEqual(Notifikasi.objects.filter(dibaca=False).get(), self.milik_lain)

    def test_perlu_login(self):
        self.client.credentials()
        self.assertEqual(self.client.get(reverse("notifikasi")).status_code, 401)
        self.assertEqual(self.client.post(reverse("notifikasi-baca-semua")).status_code, 401)

    def test_halaman_20_per_halaman(self):
        for nomor in range(25):
            layanan.kirim(self.pengguna, Notifikasi.Kategori.SISTEM, f"N{nomor}", "isi")
        data = self.client.get(reverse("notifikasi")).data
        self.assertEqual((data["count"], len(data["results"]), data["belum_dibaca"]), (27, 20, 27))
        self.assertIsNotNone(data["next"])

    def test_judul_dipotong_sesuai_panjang_kolom(self):
        notifikasi = layanan.kirim(self.pengguna, Notifikasi.Kategori.SISTEM, "J" * 200, "isi", "/" + "t" * 300)
        self.assertEqual((len(notifikasi.judul), len(notifikasi.tautan)), (150, 255))
