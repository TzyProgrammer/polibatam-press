"""Tes ubah kata sandi, lupa kata sandi, dan atur ulang lewat tautan email (revisi Tahap R)."""

import re
from datetime import datetime, timedelta
from unittest import mock

from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.notifications.models import Notifikasi
from apps.notifications.tasks import kirim_email_notifikasi

from .models import User
from .tasks import kirim_tautan_atur_ulang_sandi

SANDI = "Sandi-Lama-2026"
SANDI_BARU = "Sandi-Baru-Polibatam-7"


class DasarSandiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.pembeli = User.objects.create_user(email="pembeli@example.com", password=SANDI, nama_lengkap="Pembeli Uji")

    def masuk(self, email="pembeli@example.com", password=SANDI):
        return self.client.post(reverse("auth-login"), {"email": email, "password": password}, format="json")

    def segarkan(self, refresh):
        return self.client.post(reverse("auth-refresh"), {"refresh": refresh}, format="json")

    def judul_notifikasi(self, pengguna):
        return list(Notifikasi.objects.filter(penerima=pengguna).values_list("judul", flat=True))


class UbahSandiTests(DasarSandiTests):
    def setUp(self):
        super().setUp()
        data = self.masuk().data
        self.refresh_lama = data["refresh"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {data['access']}")

    def ubah(self, lama=SANDI, baru=SANDI_BARU):
        return self.client.post(
            reverse("auth-ubah-sandi"), {"password_lama": lama, "password_baru": baru}, format="json"
        )

    def test_wajib_masuk(self):
        self.client.credentials()
        self.assertEqual(self.ubah().status_code, 401)

    def test_sandi_lama_salah(self):
        respons = self.ubah(lama="bukan-sandinya")
        self.assertEqual(respons.status_code, 400)
        self.assertEqual(respons.data["password_lama"], ["Kata sandi saat ini salah."])

    def test_sandi_baru_harus_berbeda_dan_kuat(self):
        self.assertIn("password_baru", self.ubah(baru=SANDI).data)
        lemah = self.ubah(baru="12345678")
        self.assertEqual(lemah.status_code, 400)
        self.assertIn("password_baru", lemah.data)
        self.pembeli.refresh_from_db()
        self.assertTrue(self.pembeli.check_password(SANDI))

    def test_berhasil_sesi_lain_dikeluarkan_dan_pemberitahuan_dikirim(self):
        # Urutan penting: callback on_commit dijalankan saat captureOnCommitCallbacks selesai, sebelum patch dilepas.
        with mock.patch.object(kirim_email_notifikasi, "delay") as antre, self.captureOnCommitCallbacks(execute=True):
            respons = self.ubah()
        self.assertEqual(respons.status_code, 200)
        self.assertIn("access", respons.data)
        self.pembeli.refresh_from_db()
        self.assertTrue(self.pembeli.check_password(SANDI_BARU))
        # Refresh token lama (perangkat lain) tidak bisa dipakai lagi; token baru untuk perangkat ini berlaku.
        self.assertEqual(self.segarkan(self.refresh_lama).status_code, 401)
        self.assertEqual(self.segarkan(respons.data["refresh"]).status_code, 200)
        self.assertEqual(self.masuk().status_code, 401)
        self.assertEqual(self.masuk(password=SANDI_BARU).status_code, 200)
        notifikasi = Notifikasi.objects.get(penerima=self.pembeli)
        self.assertEqual(notifikasi.judul, "Kata sandi diubah")
        self.assertIn("halaman Profil", notifikasi.pesan)
        antre.assert_called_once_with(notifikasi.pk)


class LupaSandiTests(DasarSandiTests):
    def minta(self, email):
        with mock.patch.object(kirim_tautan_atur_ulang_sandi, "delay") as antre, self.captureOnCommitCallbacks(
            execute=True
        ):
            respons = self.client.post(reverse("auth-lupa-sandi"), {"email": email}, format="json")
        self.assertEqual(respons.status_code, 200)
        return respons, antre

    def test_jawaban_sama_untuk_email_terdaftar_dan_tidak(self):
        ada, antre_ada = self.minta("Pembeli@Example.com ")
        tidak, antre_tidak = self.minta("tidak.ada@example.com")
        self.assertEqual(ada.data, tidak.data)
        antre_ada.assert_called_once_with(self.pembeli.pk)
        antre_tidak.assert_not_called()

    def test_jeda_satu_menit_per_akun(self):
        self.minta("pembeli@example.com")
        _, antre = self.minta("pembeli@example.com")
        antre.assert_not_called()

    def test_hanya_akun_pembeli_yang_aktif(self):
        User.objects.create_superuser(email="admin@example.com", password=SANDI, nama_lengkap="Admin")
        User.objects.create_user(email="nonaktif@example.com", password=SANDI, nama_lengkap="X", is_active=False)
        for email in ("admin@example.com", "nonaktif@example.com"):
            with self.subTest(email=email):
                _, antre = self.minta(email)
                antre.assert_not_called()

    def test_email_tidak_valid_ditolak(self):
        respons = self.client.post(reverse("auth-lupa-sandi"), {"email": "bukan-email"}, format="json")
        self.assertEqual(respons.status_code, 400)

    def test_email_tautan_atur_ulang(self):
        kirim_tautan_atur_ulang_sandi(self.pembeli.pk)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["pembeli@example.com"])
        self.assertEqual(email.subject, "[Polibatam Press] Atur ulang kata sandi")
        tautan = re.search(r"http://localhost:5173/atur-ulang-sandi#uid=(\S+)&token=(\S+)", email.body)
        self.assertIsNotNone(tautan, email.body)
        self.assertIn("berlaku 60 menit", email.body)
        html, jenis = email.alternatives[0]
        self.assertEqual(jenis, "text/html")
        self.assertIn("Buat kata sandi baru", html)
        self.assertIn(tautan.group(0).replace("&", "&amp;"), html)


class AturUlangSandiTests(DasarSandiTests):
    def tautan(self, pengguna=None):
        pengguna = pengguna or self.pembeli
        return {
            "uid": urlsafe_base64_encode(force_bytes(pengguna.pk)),
            "token": default_token_generator.make_token(pengguna),
        }

    def atur_ulang(self, data):
        return self.client.post(reverse("auth-atur-ulang-sandi"), data, format="json")

    def test_cek_tautan(self):
        respons = self.client.post(reverse("auth-cek-tautan-sandi"), self.tautan(), format="json")
        self.assertEqual(respons.status_code, 200)
        self.assertEqual(respons.data["email"], "pembeli@example.com")
        for rusak in ({**self.tautan(), "token": "abc-123"}, {**self.tautan(), "uid": "!!"}, {"uid": "", "token": ""}):
            with self.subTest(rusak=rusak):
                self.assertEqual(self.client.post(reverse("auth-cek-tautan-sandi"), rusak, format="json").status_code, 400)

    def test_berhasil_sekali_pakai_dan_semua_sesi_dikeluarkan(self):
        refresh_lama = str(RefreshToken.for_user(self.pembeli))
        tautan = self.tautan()
        with mock.patch.object(kirim_email_notifikasi, "delay") as antre, self.captureOnCommitCallbacks(execute=True):
            respons = self.atur_ulang({**tautan, "password": SANDI_BARU})
        antre.assert_called_once()
        self.assertEqual(respons.status_code, 200)
        self.assertEqual(respons.data["email"], "pembeli@example.com")
        self.assertEqual(self.masuk(password=SANDI_BARU).status_code, 200)
        self.assertEqual(self.segarkan(refresh_lama).status_code, 401)
        self.assertEqual(self.judul_notifikasi(self.pembeli), ["Kata sandi diubah"])
        # Tautan yang sama tidak bisa dipakai lagi.
        ulang = self.atur_ulang({**tautan, "password": "Sandi-Lain-Lagi-99"})
        self.assertEqual(ulang.status_code, 400)
        self.assertIn("tidak valid atau sudah kedaluwarsa", str(ulang.data))

    def test_sandi_lemah_ditolak(self):
        respons = self.atur_ulang({**self.tautan(), "password": "pembeli"})
        self.assertEqual(respons.status_code, 400)
        self.assertIn("password", respons.data)
        self.pembeli.refresh_from_db()
        self.assertTrue(self.pembeli.check_password(SANDI))

    def test_tautan_kedaluwarsa_setelah_satu_jam(self):
        with mock.patch("django.contrib.auth.tokens.PasswordResetTokenGenerator._now") as sekarang:
            sekarang.return_value = datetime.now() - timedelta(minutes=61)
            tautan = self.tautan()
        self.assertEqual(self.atur_ulang({**tautan, "password": SANDI_BARU}).status_code, 400)
        with mock.patch("django.contrib.auth.tokens.PasswordResetTokenGenerator._now") as sekarang:
            sekarang.return_value = datetime.now() - timedelta(minutes=59)
            tautan = self.tautan()
        self.assertEqual(self.atur_ulang({**tautan, "password": SANDI_BARU}).status_code, 200)

    def test_akun_admin_tidak_bisa_lewat_halaman_pembeli(self):
        admin = User.objects.create_superuser(email="admin@example.com", password=SANDI, nama_lengkap="Admin")
        self.assertEqual(self.atur_ulang({**self.tautan(admin), "password": SANDI_BARU}).status_code, 400)
