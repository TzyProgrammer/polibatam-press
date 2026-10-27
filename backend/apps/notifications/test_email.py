"""Tes notifikasi yang juga dikirim ke email penerima (revisi Tahap R)."""

from unittest import mock

from celery.exceptions import Retry
from django.core import mail
from django.test import TestCase, override_settings

from apps.accounts.models import User

from . import layanan
from .models import Notifikasi
from .tasks import kirim_email_notifikasi


class EmailNotifikasiTests(TestCase):
    def setUp(self):
        self.pembeli = User.objects.create_user(email="pembeli@example.com", password="x", nama_lengkap="Sari Pembeli")

    def buat(self, **lain):
        data = {
            "penerima": self.pembeli,
            "kategori": Notifikasi.Kategori.PESANAN,
            "judul": "Pembayaran diterima",
            "pesan": 'Pesanan PP-1 sudah lunas. Ebook "Uji & Coba" bisa dibuka di Koleksi.',
            "tautan": "/pesanan/PP-1",
        }
        data.update(lain)
        return Notifikasi.objects.create(**data)

    def test_notifikasi_diantrikan_ke_email_setelah_transaksi_berhasil(self):
        with mock.patch.object(kirim_email_notifikasi, "delay") as antre:
            with self.captureOnCommitCallbacks(execute=False) as callback:
                notifikasi = layanan.kirim(self.pembeli, "pesanan", "Judul", "Pesan", "/koleksi")
            antre.assert_not_called()  # belum dikirim selama transaksi belum selesai
            for fungsi in callback:
                fungsi()
        antre.assert_called_once_with(notifikasi.pk)

    @override_settings(EMAIL_NOTIFIKASI_AKTIF=False)
    def test_email_notifikasi_bisa_dimatikan(self):
        with mock.patch.object(kirim_email_notifikasi, "delay") as antre, self.captureOnCommitCallbacks(execute=True):
            layanan.kirim(self.pembeli, "pesanan", "Judul", "Pesan")
        antre.assert_not_called()
        self.assertEqual(Notifikasi.objects.count(), 1)

    def test_isi_email(self):
        notifikasi = self.buat()
        kirim_email_notifikasi(notifikasi.pk)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["pembeli@example.com"])
        self.assertEqual(email.subject, "[Polibatam Press] Pembayaran diterima")
        self.assertIn("Halo Sari Pembeli,", email.body)
        self.assertIn('Ebook "Uji & Coba" bisa dibuka di Koleksi.', email.body)
        self.assertIn("Lihat detail: http://localhost:5173/pesanan/PP-1", email.body)
        html, jenis = email.alternatives[0]
        self.assertEqual(jenis, "text/html")
        self.assertIn("&quot;Uji &amp; Coba&quot;", html)  # isi notifikasi di-escape di HTML
        self.assertIn('href="http://localhost:5173/pesanan/PP-1"', html)
        notifikasi.refresh_from_db()
        self.assertTrue(notifikasi.email_terkirim)

    def test_tanpa_tautan_tanpa_tombol(self):
        kirim_email_notifikasi(self.buat(tautan="").pk)
        self.assertNotIn("Lihat detail", mail.outbox[0].body)
        self.assertNotIn("Lihat detail", mail.outbox[0].alternatives[0][0])

    def test_tidak_dikirim_dua_kali(self):
        notifikasi = self.buat()
        kirim_email_notifikasi(notifikasi.pk)
        kirim_email_notifikasi(notifikasi.pk)
        self.assertEqual(len(mail.outbox), 1)

    def test_akun_nonaktif_tidak_dikirimi(self):
        notifikasi = self.buat()
        User.objects.filter(pk=self.pembeli.pk).update(is_active=False)
        kirim_email_notifikasi(notifikasi.pk)
        self.assertEqual(mail.outbox, [])

    def test_smtp_gagal_dicoba_lagi(self):
        notifikasi = self.buat()
        with mock.patch("apps.notifications.tasks.kirim_email", side_effect=OSError("SMTP mati")), mock.patch.object(
            kirim_email_notifikasi, "retry", side_effect=Retry()
        ) as ulang, self.assertLogs("apps.notifications.tasks", "WARNING") as log:
            with self.assertRaises(Retry):
                kirim_email_notifikasi(notifikasi.pk)
        ulang.assert_called_once()
        self.assertNotIn("pembeli@example.com", "".join(log.output))  # alamat email tidak masuk log
        notifikasi.refresh_from_db()
        self.assertFalse(notifikasi.email_terkirim)

    def test_tombol_pemberitahuan_sandi(self):
        kirim_email_notifikasi(layanan.sandi_diubah(self.pembeli, "ubah").pk)
        self.assertIn("Atur ulang kata sandi: http://localhost:5173/lupa-sandi", mail.outbox[0].body)
