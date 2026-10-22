"""Tes Tahap C: API login JWT, registrasi, logout, dan profil (FR-01 sampai FR-04)."""

from unittest import mock

from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

from .models import User

SANDI = "Buku-Polibatam-2026"


class ApiAkunTestCase(APITestCase):
    def setUp(self):
        cache.clear()  # penghitung throttle tidak terbawa antartes
        self.pembeli = User.objects.create_user(email="budi@example.com", password=SANDI, nama_lengkap="Budi")

    def login(self, email="budi@example.com", password=SANDI):
        return self.client.post(reverse("auth-login"), {"email": email, "password": password}, format="json")

    def pakai_token(self, akses):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {akses}")


class RegistrasiTests(ApiAkunTestCase):
    def daftar(self, **data):
        isian = {"email": "siti@example.com", "nama_lengkap": "Siti Aminah", "password": SANDI, **data}
        return self.client.post(reverse("auth-registrasi"), isian, format="json")

    def test_registrasi_membuat_akun_pembeli(self):
        response = self.daftar(email="Siti@Example.com", no_telepon="0812-3456-7890")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["email"], "siti@example.com")
        self.assertEqual(response.data["role"], "pembeli")
        self.assertNotIn("password", response.data)
        pengguna = User.objects.get(email="siti@example.com")
        self.assertTrue(pengguna.check_password(SANDI))
        self.assertNotEqual(pengguna.password, SANDI)
        self.assertFalse(pengguna.is_staff)

    def test_registrasi_tidak_bisa_menjadi_admin(self):
        response = self.daftar(role="admin", is_staff=True, is_superuser=True)
        self.assertEqual(response.status_code, 201)
        pengguna = User.objects.get(email="siti@example.com")
        self.assertEqual(pengguna.role, User.Role.PEMBELI)
        self.assertFalse(pengguna.is_staff)
        self.assertFalse(pengguna.is_superuser)

    def test_email_sudah_terdaftar_tanpa_membedakan_huruf(self):
        response = self.daftar(email="BUDI@example.com")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["email"], ["Email sudah terdaftar."])

    def test_kata_sandi_lemah_ditolak(self):
        for sandi in ("12345678", "pendek", "siti@example.com"):
            with self.subTest(sandi=sandi):
                response = self.daftar(password=sandi)
                self.assertEqual(response.status_code, 400)
                self.assertIn("password", response.data)
        self.assertFalse(User.objects.filter(email="siti@example.com").exists())

    def test_isian_wajib_dan_format_telepon(self):
        response = self.client.post(reverse("auth-registrasi"), {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.data), {"email", "nama_lengkap", "password"})
        response = self.daftar(no_telepon="telepon saya")
        self.assertEqual(response.status_code, 400)
        self.assertIn("no_telepon", response.data)


class LoginTests(ApiAkunTestCase):
    def test_login_berhasil_mengembalikan_token_dan_profil(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["pengguna"]["email"], "budi@example.com")
        self.assertEqual(response.data["pengguna"]["role"], "pembeli")
        self.pembeli.refresh_from_db()
        self.assertIsNotNone(self.pembeli.last_login)

    def test_login_email_tidak_membedakan_huruf(self):
        self.assertEqual(self.login(email="  BUDI@Example.com ").status_code, 200)

    def test_login_gagal(self):
        for email, sandi in (("budi@example.com", "salah"), ("tidakada@example.com", SANDI)):
            with self.subTest(email=email):
                response = self.login(email=email, password=sandi)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.data["detail"], "Email atau kata sandi salah.")

    def test_akun_nonaktif_tidak_bisa_login_dan_tokennya_ditolak(self):
        akses = self.login().data["access"]
        self.pembeli.is_active = False
        self.pembeli.save()
        self.assertEqual(self.login().status_code, 401)
        self.pakai_token(akses)
        response = self.client.get(reverse("auth-profil"))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["code"], "user_inactive")

    def test_login_dibatasi_setelah_terlalu_banyak_percobaan(self):
        with mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {"login": "3/min"}):
            for _ in range(3):
                self.login(password="salah")
            response = self.login()
        self.assertEqual(response.status_code, 429)
        self.assertTrue(response.data["detail"].startswith("Terlalu banyak permintaan."))
        self.assertIn("Retry-After", response)


class TokenTests(ApiAkunTestCase):
    def test_refresh_merotasi_dan_mem_blacklist_token_lama(self):
        lama = self.login().data["refresh"]
        response = self.client.post(reverse("auth-refresh"), {"refresh": lama}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertNotEqual(response.data["refresh"], lama)
        # Refresh token lama tidak bisa dipakai lagi.
        response = self.client.post(reverse("auth-refresh"), {"refresh": lama}, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["code"], "token_not_valid")
        self.assertEqual(response.data["detail"], "Token tidak valid atau sudah kedaluwarsa.")

    def test_logout_mem_blacklist_refresh_token(self):
        token = self.login().data
        self.pakai_token(token["access"])
        response = self.client.post(reverse("auth-logout"), {"refresh": token["refresh"]}, format="json")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(BlacklistedToken.objects.count(), 1)
        response = self.client.post(reverse("auth-refresh"), {"refresh": token["refresh"]}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_logout_dengan_refresh_token_milik_orang_lain_ditolak(self):
        User.objects.create_user(email="siti@example.com", password=SANDI, nama_lengkap="Siti")
        milik_siti = self.login(email="siti@example.com").data["refresh"]
        self.pakai_token(self.login().data["access"])
        response = self.client.post(reverse("auth-logout"), {"refresh": milik_siti}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(BlacklistedToken.objects.exists())

    def test_logout_tanpa_login_atau_dengan_token_rusak(self):
        response = self.client.post(reverse("auth-logout"), {"refresh": "x"}, format="json")
        self.assertEqual(response.status_code, 401)
        self.pakai_token(self.login().data["access"])
        response = self.client.post(reverse("auth-logout"), {"refresh": "bukan-token"}, format="json")
        self.assertEqual(response.status_code, 400)
        response = self.client.post(reverse("auth-logout"), {}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_access_token_rusak_ditolak_dengan_pesan_indonesia(self):
        self.pakai_token("bukan.token.jwt")
        response = self.client.get(reverse("auth-profil"))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.data, {"detail": "Token tidak valid atau sudah kedaluwarsa.", "code": "token_not_valid"}
        )


class ProfilTests(ApiAkunTestCase):
    def test_lihat_profil(self):
        self.pakai_token(self.login().data["access"])
        response = self.client.get(reverse("auth-profil"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {"id": self.pembeli.pk, "email": "budi@example.com", "nama_lengkap": "Budi", "no_telepon": "",
             "alamat": "", "role": "pembeli"},
        )

    def test_ubah_profil_tanpa_bisa_mengubah_email_dan_peran(self):
        self.pakai_token(self.login().data["access"])
        response = self.client.patch(
            reverse("auth-profil"),
            {"nama_lengkap": "Budi Santoso", "no_telepon": "+62 812 3456 7890", "alamat": "Batam Centre",
             "email": "lain@example.com", "role": "admin"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.pembeli.refresh_from_db()
        self.assertEqual(self.pembeli.nama_lengkap, "Budi Santoso")
        self.assertEqual(self.pembeli.no_telepon, "+62 812 3456 7890")
        self.assertEqual(self.pembeli.alamat, "Batam Centre")
        self.assertEqual(self.pembeli.email, "budi@example.com")
        self.assertEqual(self.pembeli.role, User.Role.PEMBELI)

    def test_profil_perlu_login_dan_put_tidak_diizinkan(self):
        response = self.client.get(reverse("auth-profil"))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["detail"], "Data autentikasi tidak diberikan.")
        self.pakai_token(self.login().data["access"])
        response = self.client.put(reverse("auth-profil"), {"nama_lengkap": "X"}, format="json")
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.data["detail"], "Metode PUT tidak diizinkan.")
