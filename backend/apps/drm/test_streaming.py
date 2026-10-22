"""Tes Tahap C: sesi streaming bertoken, playlist per sesi, dan distribusi kunci AES-128."""

import re
import uuid
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import User
from apps.catalog.models import Buku, Produk
from apps.orders.models import ItemPesanan, Pesanan
from core.testing import KUNCI_INDUK_UJI, STORAGES_MEMORI, PenyimpananMemoriUji, berkas_uji

from .kode import hash_token
from .kunci import enkripsi_kunci
from .models import HakAkses, LogAksesKunci, PaketAudio, SesiStreaming
from .streaming import umur_segmen
from .tasks import kemas_audiobook

IV_HEX = "000102030405060708090a0b0c0d0e0f"
PLAYLIST = f"""#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:10
#EXT-X-MEDIA-SEQUENCE:0
#EXT-X-PLAYLIST-TYPE:VOD
#EXT-X-KEY:METHOD=AES-128,URI="kunci",IV=0x{IV_HEX}
#EXTINF:10.000000,
seg_00000.ts
#EXTINF:10.000000,
seg_00001.ts
#EXTINF:5.000000,
seg_00002.ts
#EXT-X-ENDLIST
"""
POLA_URL_PLAYLIST = re.compile(r"^http://testserver/api/drm/stream/(?P<token>[A-Za-z0-9_-]{43})/playlist\.m3u8$")
KUNCI_UJI = bytes(range(16))


def buat_audiobook_siap(judul="Audiobook Uji", kunci=KUNCI_UJI):
    """Audiobook dengan paket HLS siap (playlist di penyimpanan memori, tanpa menjalankan ffmpeg)."""
    buku = Buku.objects.create(judul=judul, penulis="Penulis")
    with mock.patch.object(kemas_audiobook, "delay"):
        produk = Produk.objects.create(
            buku=buku, format=Produk.Format.AUDIOBOOK, harga=60000, berkas=berkas_uji("audio.mp3")
        )
    paket = produk.paket_audio
    paket.prefix_hls = f"hls/{uuid.uuid4().hex}"
    default_storage.save(f"{paket.prefix_hls}/index.m3u8", ContentFile(PLAYLIST.encode()))
    paket.status = PaketAudio.Status.SIAP
    paket.kunci_terenkripsi = enkripsi_kunci(kunci)
    paket.jumlah_segmen = 3
    paket.durasi_detik = 25
    paket.save()
    return produk


def beri_hak_akses(pembeli, produk):
    pesanan = Pesanan.objects.create(pembeli=pembeli, status_pembayaran=Pesanan.StatusPembayaran.LUNAS)
    item = ItemPesanan.objects.create(
        pesanan=pesanan, produk=produk, judul=produk.buku.judul, format=produk.format, harga_satuan=produk.harga
    )
    return HakAkses.objects.create(pembeli=pembeli, produk=produk, item_pesanan=item)


@override_settings(STORAGES=STORAGES_MEMORI, FERNET_MASTER_KEY=KUNCI_INDUK_UJI, STREAMING_SESSION_MINUTES=10)
class StreamingTestCase(APITestCase):
    def setUp(self):
        cache.clear()
        self.kunci = KUNCI_UJI
        self.pemilik = User.objects.create_user(email="pemilik@example.com", password="x", nama_lengkap="Pemilik")
        self.lain = User.objects.create_user(email="lain@example.com", password="x", nama_lengkap="Lain")
        self.produk = buat_audiobook_siap(kunci=self.kunci)
        self.paket = self.produk.paket_audio
        self.hak = beri_hak_akses(self.pemilik, self.produk)

    def login(self, pengguna):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(pengguna)}")

    def tanpa_login(self):
        self.client.credentials()

    def url_sesi(self, produk=None):
        return reverse("drm-sesi-baru", args=[(produk or self.produk).pk])

    def buat_sesi(self, pengguna=None):
        """Membuat sesi lewat API; mengembalikan (token, sesi) dan membiarkan klien login sebagai pengguna."""
        self.login(pengguna or self.pemilik)
        response = self.client.post(self.url_sesi())
        self.assertEqual(response.status_code, 201, response.data)
        token = POLA_URL_PLAYLIST.match(response.data["playlist"])["token"]
        return token, SesiStreaming.objects.get(token_hash=hash_token(token))


class SesiStreamingBaruTests(StreamingTestCase):
    def test_pemilik_mendapat_sesi_bertoken(self):
        sebelum = timezone.now()
        self.login(self.pemilik)
        response = self.client.post(self.url_sesi(), HTTP_USER_AGENT="Peramban Uji")
        self.assertEqual(response.status_code, 201)
        self.assertIn("no-store", response["Cache-Control"])
        cocok = POLA_URL_PLAYLIST.match(response.data["playlist"])
        self.assertIsNotNone(cocok, response.data["playlist"])
        token = cocok["token"]
        sesi = SesiStreaming.objects.get()
        # Basis data hanya menyimpan hash token.
        self.assertEqual(sesi.token_hash, hash_token(token))
        self.assertNotEqual(sesi.token_hash, token)
        self.assertEqual(sesi.pembeli, self.pemilik)
        self.assertEqual(sesi.paket, self.paket)
        self.assertEqual(sesi.alamat_ip, "127.0.0.1")
        self.assertEqual(sesi.user_agent, "Peramban Uji")
        self.assertTrue(sebelum + timedelta(minutes=10) <= sesi.kedaluwarsa <= timezone.now() + timedelta(minutes=10))
        self.assertEqual(response.data["kedaluwarsa"], sesi.kedaluwarsa)

    def test_sesi_baru_mencabut_sesi_lama(self):
        _, lama = self.buat_sesi()
        _, baru = self.buat_sesi()
        lama.refresh_from_db()
        self.assertTrue(lama.dicabut)
        self.assertFalse(baru.dicabut)

    def test_ip_dari_header_nginx(self):
        self.login(self.pemilik)
        self.client.post(self.url_sesi(), HTTP_X_REAL_IP="203.0.113.7")
        self.client.post(self.url_sesi(), HTTP_X_REAL_IP="bukan-ip")
        self.assertEqual(
            list(SesiStreaming.objects.order_by("dibuat", "pk").values_list("alamat_ip", flat=True)),
            ["203.0.113.7", "127.0.0.1"],
        )

    def test_penolakan_membuat_sesi(self):
        ebook = Produk.objects.create(
            buku=self.produk.buku, format=Produk.Format.EBOOK, harga=40000, berkas=berkas_uji("buku.pdf")
        )
        self.tanpa_login()
        self.assertEqual(self.client.post(self.url_sesi()).status_code, 401)
        self.login(self.lain)
        response = self.client.post(self.url_sesi())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["detail"], "Anda tidak memiliki hak akses ke audiobook ini.")
        self.login(self.pemilik)
        response = self.client.post(self.url_sesi(ebook))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], "Audiobook tidak ditemukan.")
        self.assertEqual(self.client.post(reverse("drm-sesi-baru", args=[999999])).status_code, 404)
        self.hak.aktif = False
        self.hak.save()
        self.assertEqual(self.client.post(self.url_sesi()).status_code, 403)
        self.hak.aktif = True
        self.hak.save()
        self.paket.status = PaketAudio.Status.DIPROSES
        self.paket.save()
        response = self.client.post(self.url_sesi())
        self.assertEqual(response.status_code, 409)
        self.assertFalse(SesiStreaming.objects.exists())

    def test_pembuatan_sesi_dibatasi(self):
        self.login(self.pemilik)
        with mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {"sesi_streaming": "2/min"}):
            for _ in range(2):
                self.assertEqual(self.client.post(self.url_sesi()).status_code, 201)
            self.assertEqual(self.client.post(self.url_sesi()).status_code, 429)


class PlaylistTests(StreamingTestCase):
    def test_playlist_per_sesi_ditulis_ulang(self):
        token, _ = self.buat_sesi()
        response = self.client.get(reverse("drm-playlist", args=[token]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/vnd.apple.mpegurl")
        self.assertIn("no-store", response["Cache-Control"])
        isi = response.content.decode()
        url_kunci = f"http://testserver/api/drm/stream/{token}/kunci"
        self.assertIn(f'#EXT-X-KEY:METHOD=AES-128,URI="{url_kunci}",IV=0x{IV_HEX}', isi)
        self.assertNotIn('URI="kunci"', isi)
        segmen = [baris for baris in isi.splitlines() if baris and not baris.startswith("#")]
        umur = 25 + 30 * 60  # durasi audio + 30 menit
        self.assertEqual(
            segmen,
            [
                f"{PenyimpananMemoriUji.BASIS_URL}{self.paket.prefix_hls}/seg_0000{i}.ts"
                f"?X-Amz-Expires={umur}&X-Amz-Signature=uji"
                for i in range(3)
            ],
        )
        # Playlist asli di penyimpanan tidak berubah.
        with default_storage.open(f"{self.paket.prefix_hls}/index.m3u8") as berkas:
            self.assertEqual(berkas.read().decode(), PLAYLIST)

    def test_penolakan_playlist_tidak_dicatat_di_log_kunci(self):
        token, sesi = self.buat_sesi()
        url = reverse("drm-playlist", args=[token])
        self.tanpa_login()
        self.assertEqual(self.client.get(url).status_code, 401)
        self.login(self.lain)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.login(self.pemilik)
        self.assertEqual(self.client.get(reverse("drm-playlist", args=["token-acak"])).status_code, 404)
        sesi.kedaluwarsa = timezone.now() - timedelta(seconds=1)
        sesi.save()
        self.assertEqual(self.client.get(url).status_code, 410)
        self.assertFalse(LogAksesKunci.objects.exists())

    def test_umur_presigned_url_segmen(self):
        self.paket.durasi_detik = 0
        self.assertEqual(umur_segmen(self.paket), 30 * 60)
        self.paket.durasi_detik = 10 * 60 * 60  # audiobook 10 jam: dibatasi 6 jam
        self.assertEqual(umur_segmen(self.paket), 6 * 60 * 60)
        self.paket.durasi_detik = 0
        with self.settings(STREAMING_SESSION_MINUTES=45):  # tidak lebih pendek dari umur sesi
            self.assertEqual(umur_segmen(self.paket), 45 * 60)


class KunciTests(StreamingTestCase):
    def url_kunci(self, token):
        return reverse("drm-kunci", args=[token])

    def assert_ditolak(self, response, kode, alasan, pengguna=None, sesi=None):
        self.assertEqual(response.status_code, kode)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertNotIn(self.kunci, response.content)
        log = LogAksesKunci.objects.get()
        self.assertEqual(log.hasil, LogAksesKunci.Hasil.DITOLAK)
        self.assertEqual(log.alasan, alasan)
        self.assertEqual(log.pengguna, pengguna)
        self.assertEqual(log.sesi, sesi)
        self.assertEqual(log.paket, sesi.paket if sesi else None)
        self.assertEqual(log.alamat_ip, "127.0.0.1")

    def test_pemilik_menerima_kunci_dan_tercatat(self):
        token, sesi = self.buat_sesi()
        response = self.client.get(self.url_kunci(token))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, self.kunci)
        self.assertEqual(response["Content-Type"], "application/octet-stream")
        self.assertIn("no-store", response["Cache-Control"])
        log = LogAksesKunci.objects.get()
        self.assertEqual(
            (log.hasil, log.sesi, log.pengguna, log.paket, log.alamat_ip),
            (LogAksesKunci.Hasil.DIIZINKAN, sesi, self.pemilik, self.paket, "127.0.0.1"),
        )

    def test_tanpa_login(self):
        token, sesi = self.buat_sesi()
        self.tanpa_login()
        response = self.client.get(self.url_kunci(token))
        self.assert_ditolak(response, 401, "tanpa login", sesi=sesi)
        self.assertEqual(response["WWW-Authenticate"], 'Bearer realm="api"')

    def test_jwt_tidak_valid(self):
        token, sesi = self.buat_sesi()
        self.client.credentials(HTTP_AUTHORIZATION="Bearer bukan.jwt.valid")
        self.assert_ditolak(self.client.get(self.url_kunci(token)), 401, "JWT tidak valid", sesi=sesi)

    def test_token_acak(self):
        self.login(self.pemilik)
        with self.assertLogs("django.request", level="WARNING") as log:
            response = self.client.get(self.url_kunci("tokenacak123"))
        self.assert_ditolak(response, 404, "token tidak dikenal", self.pemilik)
        # Token pada URL disamarkan di log Django.
        self.assertEqual(log.records[0].getMessage(), "Not Found: /api/drm/stream/***/kunci")

    def test_pengguna_lain(self):
        token, sesi = self.buat_sesi()
        self.login(self.lain)
        self.assert_ditolak(self.client.get(self.url_kunci(token)), 403, "bukan pemilik sesi", self.lain, sesi)

    def test_sesi_dicabut(self):
        token, sesi = self.buat_sesi()
        self.buat_sesi()  # sesi baru mencabut sesi pertama
        self.assert_ditolak(self.client.get(self.url_kunci(token)), 410, "sesi dicabut", self.pemilik, sesi)

    def test_sesi_kedaluwarsa(self):
        token, sesi = self.buat_sesi()
        with mock.patch("django.utils.timezone.now", return_value=sesi.kedaluwarsa + timedelta(seconds=1)):
            response = self.client.get(self.url_kunci(token))
        self.assert_ditolak(response, 410, "sesi kedaluwarsa", self.pemilik, sesi)

    def test_hak_akses_dicabut(self):
        token, sesi = self.buat_sesi()
        self.hak.aktif = False
        self.hak.save()
        self.assert_ditolak(self.client.get(self.url_kunci(token)), 403, "hak akses dicabut", self.pemilik, sesi)

    def test_paket_sedang_diproses_ulang(self):
        token, sesi = self.buat_sesi()
        self.paket.status = PaketAudio.Status.DIPROSES
        self.paket.save()
        self.assert_ditolak(self.client.get(self.url_kunci(token)), 409, "paket belum siap", self.pemilik, sesi)

    def test_permintaan_kunci_dibatasi(self):
        token, _ = self.buat_sesi()
        with mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {"kunci": "2/min"}):
            for _ in range(2):
                self.assertEqual(self.client.get(self.url_kunci(token)).status_code, 200)
            self.assertEqual(self.client.get(self.url_kunci(token)).status_code, 429)


class HalamanUjiPemutarTests(TestCase):
    def test_hanya_tersedia_saat_debug(self):
        self.assertEqual(self.client.get(reverse("uji-pemutar")).status_code, 404)
        with self.settings(DEBUG=True):
            response = self.client.get(reverse("uji-pemutar"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "https://cdn.jsdelivr.net/npm/hls.js@1.7.3/dist/hls.min.js")
        self.assertContains(response, 'integrity="sha384-')
        self.assertContains(response, "xhrSetup")


@override_settings(STORAGES=STORAGES_MEMORI, FERNET_MASTER_KEY=KUNCI_INDUK_UJI)
class BuatAksesUjiTests(TestCase):
    def setUp(self):
        self.pembeli = User.objects.create_user(email="pembeli@example.com", password="x", nama_lengkap="Pembeli")
        self.produk = buat_audiobook_siap()

    def jalankan(self, *argumen):
        keluaran = StringIO()
        call_command("buat_akses_uji", *argumen, stdout=keluaran)
        return keluaran.getvalue()

    def test_hanya_saat_debug(self):
        with self.assertRaises(CommandError):
            self.jalankan("--email", "pembeli@example.com", "--produk", str(self.produk.pk))
        self.assertFalse(HakAkses.objects.exists())

    @override_settings(DEBUG=True)
    def test_membuat_hak_akses_dengan_pesanan_uji(self):
        teks = self.jalankan("--email", "PEMBELI@example.com", "--produk", str(self.produk.pk))
        hak = HakAkses.objects.get(pembeli=self.pembeli, produk=self.produk)
        pesanan = hak.item_pesanan.pesanan
        self.assertTrue(hak.aktif)
        self.assertEqual(pesanan.status_pembayaran, Pesanan.StatusPembayaran.LUNAS)
        self.assertEqual(pesanan.midtrans_payment_type, "uji-lokal")
        self.assertEqual(pesanan.total, self.produk.harga)
        self.assertIn(f"/uji-pemutar/?produk={self.produk.pk}", teks)
        # Dijalankan ulang: tidak membuat pesanan baru.
        self.jalankan("--email", "pembeli@example.com", "--produk", str(self.produk.pk))
        self.assertEqual(Pesanan.objects.count(), 1)

    @override_settings(DEBUG=True)
    def test_cabut_lalu_aktifkan_lagi(self):
        argumen = ("--email", "pembeli@example.com", "--produk", str(self.produk.pk))
        self.jalankan(*argumen)
        self.jalankan(*argumen, "--cabut")
        self.assertFalse(HakAkses.objects.get().aktif)
        self.jalankan(*argumen)
        self.assertTrue(HakAkses.objects.get().aktif)

    @override_settings(DEBUG=True)
    def test_daftar_audiobook_dan_validasi(self):
        teks = self.jalankan()
        self.assertIn(f"[{self.produk.pk}] Audiobook Uji — Siap diputar", teks)
        ebook = Produk.objects.create(
            buku=self.produk.buku, format=Produk.Format.EBOOK, harga=40000, berkas=berkas_uji("a.pdf")
        )
        for argumen in (
            ("--produk", str(self.produk.pk)),
            ("--email", "tidakada@example.com", "--produk", str(self.produk.pk)),
            ("--email", "pembeli@example.com", "--produk", str(ebook.pk)),
            ("--email", "pembeli@example.com", "--produk", "999999"),
            ("--email", "pembeli@example.com", "--produk", str(self.produk.pk), "--cabut"),
        ):
            with self.subTest(argumen=argumen), self.assertRaises(CommandError):
                self.jalankan(*argumen)
        self.assertFalse(HakAkses.objects.exists())


@override_settings(STORAGES=STORAGES_MEMORI, FERNET_MASTER_KEY=KUNCI_INDUK_UJI)
class AdminDRMTests(TestCase):
    def setUp(self):
        admin = User.objects.create_superuser(email="admin@example.com", password="x", nama_lengkap="Admin")
        self.client.force_login(admin)
        self.produk = buat_audiobook_siap()
        self.paket = self.produk.paket_audio

    def test_paket_audio_hanya_bisa_dilihat(self):
        response = self.client.get(reverse("admin:drm_paketaudio_change", args=[self.paket.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="_save"')
        self.assertNotContains(response, 'name="_continue"')
        self.assertNotContains(response, 'name="_addanother"')
        self.assertNotContains(response, 'class="deletelink"')
        self.assertContains(response, 'class="closelink"')
        response = self.client.get(reverse("admin:drm_paketaudio_changelist"))
        self.assertContains(response, 'value="proses_ulang"')
        self.assertNotContains(response, 'value="delete_selected"')
        response = self.client.get(reverse("admin:drm_paketaudio_delete", args=[self.paket.pk]))
        self.assertEqual(response.status_code, 403)

    def test_halaman_ubah_lain_memakai_satu_tombol(self):
        pembeli = User.objects.create_user(email="p@example.com", password="x", nama_lengkap="P")
        hak = beri_hak_akses(pembeli, self.produk)
        response = self.client.get(reverse("admin:drm_hakakses_change", args=[hak.pk]))
        self.assertContains(response, 'value="Simpan Perubahan"')
        self.assertNotContains(response, 'name="_continue"')
        self.assertNotContains(response, 'name="_addanother"')

    def test_buku_audiobook_tetap_bisa_dihapus_dari_admin(self):
        buku = self.produk.buku
        prefix = self.paket.prefix_hls
        url = reverse("admin:catalog_buku_delete", args=[buku.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["perms_lacking"])
        self.assertFalse(response.context["protected"])
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(url, {"post": "yes"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Buku.objects.filter(pk=buku.pk).exists())
        self.assertFalse(PaketAudio.objects.exists())
        try:
            sisa = default_storage.listdir(prefix)[1]
        except FileNotFoundError:
            sisa = []
        self.assertEqual(sisa, [])
