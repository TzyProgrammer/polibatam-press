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


class LupaSandiAdminTests(TestCase):
    """Lupa kata sandi Django Admin: hanya akun admin, dibatasi per IP, dan sesi lama diakhiri."""

    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.admin = User.objects.create_superuser(email="admin@example.com", password="Sandi-Admin-2026", nama_lengkap="Admin")

    def minta(self, email, **meta):
        return self.client.post(reverse("admin_password_reset"), {"email": email}, **meta)

    def test_tautan_lupa_sandi_di_halaman_masuk(self):
        masuk = self.client.get(reverse("admin:login"))
        self.assertContains(masuk, f'<a href="{reverse("admin_password_reset")}">Lupa Password?</a>', html=True)
        self.assertContains(masuk, 'id="login-form"')
        halaman = self.client.get(reverse("admin_password_reset"))
        self.assertEqual(halaman.status_code, 200)
        self.assertContains(halaman, "merek__logo")  # memakai tampilan admin Polibatam Press

    def test_email_dikirim_hanya_untuk_admin(self):
        from django.core import mail

        User.objects.create_user(email="pembeli@example.com", password="x", nama_lengkap="Pembeli")
        self.assertRedirects(self.minta("pembeli@example.com"), reverse("password_reset_done"))
        self.assertEqual(mail.outbox, [])
        self.assertRedirects(self.minta("admin@example.com"), reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.subject, "[Polibatam Press] Atur ulang kata sandi admin")
        self.assertIn("http://testserver/admin/atur-ulang-sandi/", email.body)
        self.assertIn("berlaku 60 menit", email.body)
        self.assertIn("Buat kata sandi baru", email.alternatives[0][0])

    def test_dibatasi_lima_permintaan_per_jam_per_ip(self):
        from django.core import mail

        for _ in range(7):
            self.minta("admin@example.com", HTTP_X_FORWARDED_FOR="203.0.113.5")
        self.assertEqual(len(mail.outbox), 5)
        self.minta("admin@example.com", HTTP_X_FORWARDED_FOR="203.0.113.9")  # IP lain tidak terpengaruh
        self.assertEqual(len(mail.outbox), 6)

    def test_atur_ulang_mengakhiri_sesi_jwt_dan_memberi_tahu(self):
        import re

        from django.core import mail
        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
        from rest_framework_simplejwt.tokens import RefreshToken

        from apps.notifications.models import Notifikasi

        refresh = RefreshToken.for_user(self.admin)
        self.minta("admin@example.com")
        path = re.search(r"http://testserver(/admin/atur-ulang-sandi/\S+/)", mail.outbox[0].body).group(1)
        halaman = self.client.get(path, follow=True)  # Django memindahkan token ke sesi lalu mengalihkan
        self.assertContains(halaman, "new_password1")
        respons = self.client.post(
            halaman.redirect_chain[-1][0], {"new_password1": "Sandi-Baru-Admin-9", "new_password2": "Sandi-Baru-Admin-9"}
        )
        self.assertRedirects(respons, reverse("password_reset_complete"))
        selesai = self.client.get(reverse("password_reset_complete"))
        self.assertContains(selesai, f'href="{reverse("admin:login")}"')
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("Sandi-Baru-Admin-9"))
        self.assertTrue(BlacklistedToken.objects.filter(token__jti=refresh["jti"]).exists())
        self.assertEqual(Notifikasi.objects.get(penerima=self.admin).judul, "Kata sandi diubah")


class GantiSandiAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email="admin@example.com", password="Sandi-Admin-2026", nama_lengkap="Admin")
        self.client.force_login(self.admin)

    def test_ganti_sandi_sendiri_memberi_tahu(self):
        from apps.notifications.models import Notifikasi

        data = {"old_password": "Sandi-Admin-2026", "new_password1": "Sandi-Baru-Admin-9", "new_password2": "Sandi-Baru-Admin-9"}
        self.assertEqual(self.client.post(reverse("admin:password_change"), {**data, "old_password": "salah"}).status_code, 200)
        self.assertFalse(Notifikasi.objects.exists())
        self.assertRedirects(self.client.post(reverse("admin:password_change"), data), reverse("admin:password_change_done"))
        notifikasi = Notifikasi.objects.get(penerima=self.admin)
        self.assertIn("akun admin Anda baru saja diubah", notifikasi.pesan)

    def test_admin_mengganti_sandi_pembeli(self):
        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
        from rest_framework_simplejwt.tokens import RefreshToken

        from apps.notifications.models import Notifikasi

        pembeli = User.objects.create_user(email="pembeli@example.com", password="x", nama_lengkap="Pembeli")
        refresh = RefreshToken.for_user(pembeli)
        url = reverse("admin:auth_user_password_change", args=[pembeli.pk])
        respons = self.client.post(
            url, {"password1": "Sandi-Dari-Admin-5", "password2": "Sandi-Dari-Admin-5", "usable_password": "true"}
        )
        self.assertEqual(respons.status_code, 302, getattr(respons, "context", None) and respons.context["form"].errors)
        pembeli.refresh_from_db()
        self.assertTrue(pembeli.check_password("Sandi-Dari-Admin-5"))
        self.assertTrue(BlacklistedToken.objects.filter(token__jti=refresh["jti"]).exists())
        self.assertIn("diubah oleh admin Polibatam Press", Notifikasi.objects.get(penerima=pembeli).pesan)
