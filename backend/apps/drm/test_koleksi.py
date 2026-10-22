"""Tes Tahap F: API koleksi digital pembeli (FR-13)."""

from unittest import mock

from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.orders.models import ItemPesanan, Pesanan
from apps.orders.testing import buat_pembeli, buat_produk_uji
from core.testing import STORAGES_MEMORI

from .layanan import berikan_hak_akses
from .models import HakAkses, PaketAudio, SalinanEbook
from .tasks import buat_salinan_ebook


@override_settings(STORAGES=STORAGES_MEMORI)
class KoleksiTests(APITestCase):
    def setUp(self):
        self.pembeli = buat_pembeli()
        self.cetak, self.ebook, self.audio = buat_produk_uji()
        self.pesanan = Pesanan.objects.create(pembeli=self.pembeli, status_pembayaran=Pesanan.StatusPembayaran.LUNAS)
        for produk in (self.cetak, self.ebook, self.audio):
            item = ItemPesanan.objects.create(
                pesanan=self.pesanan, produk=produk, judul=produk.buku.judul, format=produk.format,
                harga_satuan=produk.harga,
            )
            with mock.patch.object(buat_salinan_ebook, "delay"):
                berikan_hak_akses(item)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.pembeli)}")

    def koleksi(self):
        response = self.client.get(reverse("koleksi"))
        self.assertEqual(response.status_code, 200)
        return {k["format"]: k for k in response.data}

    def test_koleksi_berisi_produk_digital_milik_pembeli(self):
        koleksi = self.koleksi()
        self.assertEqual(set(koleksi), {"ebook", "audiobook"})  # buku cetak tidak masuk koleksi
        ebook = koleksi["ebook"]
        self.assertEqual(ebook["produk_id"], self.ebook.pk)
        self.assertEqual(ebook["buku"]["judul"], "Keamanan Data Modern")
        self.assertEqual((ebook["status"], ebook["keterangan"]), ("menunggu", "Menunggu diproses"))
        self.assertEqual(ebook["url_akses"], f"/api/drm/ebook/{self.ebook.pk}/")
        self.assertEqual(ebook["nomor_pesanan"], self.pesanan.nomor)
        audio = koleksi["audiobook"]
        self.assertEqual((audio["status"], audio["keterangan"]), ("siap", "Siap diputar"))
        self.assertEqual(audio["url_akses"], f"/api/drm/audiobook/{self.audio.pk}/sesi/")
        self.assertTrue(audio["aktif"])

        SalinanEbook.objects.update(status=SalinanEbook.Status.SIAP)
        self.assertEqual(self.koleksi()["ebook"]["keterangan"], "Siap dibaca")

    def test_status_dicabut_dan_paket_diproses_ulang(self):
        HakAkses.objects.filter(produk=self.ebook).update(aktif=False)
        PaketAudio.objects.filter(produk=self.audio).update(status=PaketAudio.Status.DIPROSES)
        koleksi = self.koleksi()
        self.assertEqual(
            (koleksi["ebook"]["aktif"], koleksi["ebook"]["status"], koleksi["ebook"]["keterangan"]),
            (False, "dicabut", "Akses dinonaktifkan admin"),
        )
        self.assertEqual(koleksi["audiobook"]["status"], "diproses")

    def test_hanya_milik_sendiri_dan_perlu_login(self):
        lain = buat_pembeli("lain@example.com")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(lain)}")
        self.assertEqual(self.client.get(reverse("koleksi")).data, [])
        self.client.credentials()
        self.assertEqual(self.client.get(reverse("koleksi")).status_code, 401)

    def test_tanpa_kueri_berulang(self):
        with self.assertNumQueries(2):  # pengguna (JWT) + hak akses beserta produk, paket, salinan, pesanan
            self.client.get(reverse("koleksi"))
