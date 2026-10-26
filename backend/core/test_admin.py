"""Tes tampilan dan keamanan sesi Django Admin (revisi Tahap R, 26 Oktober)."""

import time

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from core.sesi import KUNCI_AKTIF_TERAKHIR


class MenuAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email="admin@example.com", password="x", nama_lengkap="Admin")
        self.client.force_login(self.admin)

    def test_menu_beranda_dikelompokkan_sesuai_urutan_pemilik(self):
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        menu = [(app["name"], [m["name"] for m in app["models"]]) for app in response.context["app_list"]]
        self.assertEqual(
            menu,
            [
                ("Katalog", ["Kategori", "Buku"]),
                ("ISBN", ["Pengajuan ISBN"]),
                ("Pesanan", ["Pesanan"]),
                ("Konten Digital (DRM)", ["Hak akses", "Lacak kebocoran"]),
                ("Akun", ["Pengguna"]),
                ("Autentikasi dan Otorisasi", ["Grup"]),
                (
                    "Log",
                    [
                        "Salinan ebook",
                        "Paket audio (HLS)",
                        "Sesi streaming",
                        "Notifikasi",
                        "Log notifikasi Midtrans",
                        "Log akses kunci",
                        "Blacklisted Tokens",
                        "Outstanding Tokens",
                    ],
                ),
            ],
        )
        # Menu kiri memakai susunan yang sama.
        self.assertEqual(
            [app["name"] for app in response.context["available_apps"]], [nama for nama, _ in menu]
        )

    def test_bagian_gabungan_tanpa_tautan_dan_alamat_model_tetap(self):
        response = self.client.get(reverse("admin:index"))
        self.assertContains(response, '<span class="section">Log</span>', html=True)
        self.assertContains(response, reverse("admin:drm_salinanebook_changelist"))
        self.assertContains(response, reverse("admin:app_list", kwargs={"app_label": "catalog"}))

    def test_halaman_indeks_app_tetap_menampilkan_model_app_itu(self):
        response = self.client.get(reverse("admin:app_list", kwargs={"app_label": "drm"}))
        self.assertEqual(response.status_code, 200)
        nama = [m["name"] for m in response.context["app_list"][0]["models"]]
        self.assertIn("Lacak kebocoran", nama)
        self.assertIn("Salinan ebook", nama)

    def test_logo_dan_lihat_situs_ke_halaman_pembeli(self):
        response = self.client.get(reverse("admin:index"))
        self.assertContains(response, "polibatam/logo-polibatam-press.jpg")
        self.assertContains(response, f'<a href="{settings.FRONTEND_URL}">Lihat situs</a>', html=True)
        self.assertNotContains(response, '<a href="/admin/">Admin Marketplace Polibatam Press</a>', html=True)


class HalamanMasukAdminTests(TestCase):
    def test_logo_dan_latar_di_halaman_masuk(self):
        response = self.client.get(reverse("admin:login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="merek__logo"')
        self.assertContains(response, "polibatam/admin.css")
        # Pengatur sesi hanya untuk admin yang sudah masuk.
        self.assertNotContains(response, "admin-sesi.js")


class SesiAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email="admin@example.com", password="x", nama_lengkap="Admin")
        self.client.force_login(self.admin)

    def mundurkan_aktivitas(self, menit):
        sesi = self.client.session
        sesi[KUNCI_AKTIF_TERAKHIR] = int(time.time()) - menit * 60
        sesi.save()

    def test_cookie_sesi_berakhir_saat_peramban_ditutup(self):
        self.assertTrue(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)
        response = self.client.get(reverse("admin:index"))
        cookie = response.cookies[settings.SESSION_COOKIE_NAME]
        self.assertEqual(cookie["max-age"], "")
        self.assertEqual(cookie["expires"], "")

    def test_sesi_aktif_tidak_terganggu(self):
        self.mundurkan_aktivitas(29)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

    def test_sesi_diakhiri_setelah_30_menit_tidak_aktif(self):
        self.mundurkan_aktivitas(31)
        response = self.client.get(reverse("admin:drm_hakakses_changelist"), follow=True)
        login = reverse("admin:login")
        self.assertEqual(response.redirect_chain[0][0], f"{login}?next=/admin/drm/hakakses/")
        self.assertContains(response, "Sesi admin berakhir karena tidak ada aktivitas selama 30 menit.")
        # Benar-benar keluar: halaman admin berikutnya meminta masuk lagi.
        self.assertRedirects(
            self.client.get(reverse("admin:index")), f"{login}?next=/admin/", fetch_redirect_response=False
        )

    @override_settings(ADMIN_SESI_TIDAK_AKTIF_MENIT=5)
    def test_batas_waktu_bisa_diatur(self):
        self.mundurkan_aktivitas(6)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 302)

    def test_ping_memperbarui_aktivitas(self):
        self.mundurkan_aktivitas(20)
        self.assertEqual(self.client.get(reverse("admin:sesi_aktif")).status_code, 204)
        self.assertGreater(self.client.session[KUNCI_AKTIF_TERAKHIR], int(time.time()) - 5)

    def test_ping_setelah_sesi_berakhir_ditolak_tanpa_dialihkan(self):
        self.mundurkan_aktivitas(31)
        self.assertEqual(self.client.get(reverse("admin:sesi_aktif")).status_code, 401)

    def test_pengatur_sesi_dimuat_untuk_admin(self):
        response = self.client.get(reverse("admin:index"))
        self.assertContains(response, 'src="/static/polibatam/admin-sesi.js" data-menit="30"')

    def test_api_pembeli_tidak_terpengaruh(self):
        # Middleware hanya mengatur /admin/; API pembeli memakai JWT.
        self.mundurkan_aktivitas(31)
        self.assertEqual(self.client.get("/api/katalog/kategori/").status_code, 200)
