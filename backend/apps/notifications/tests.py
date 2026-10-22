from django.test import TestCase

from apps.accounts.models import User

from .models import Notifikasi


class NotifikasiTests(TestCase):
    def test_baru_belum_dibaca_dan_terbaru_di_atas(self):
        user = User.objects.create_user(email="pembeli@example.com", password="x", nama_lengkap="Pembeli")
        lama = Notifikasi.objects.create(penerima=user, judul="Lama", pesan="a")
        baru = Notifikasi.objects.create(penerima=user, judul="Baru", pesan="b")
        self.assertFalse(baru.dibaca)
        self.assertFalse(baru.email_terkirim)
        self.assertEqual(list(user.notifikasi.all()), [baru, lama])
