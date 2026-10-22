"""Tes Tahap B: pengemasan audiobook menjadi HLS terenkripsi AES-128."""

import shutil
import subprocess
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock, skipUnless

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from django.core.exceptions import ImproperlyConfigured
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.catalog.models import Buku, Produk
from core.testing import KUNCI_INDUK_UJI, STORAGES_MEMORI, berkas_uji

from . import hls
from .kunci import dekripsi_kunci, enkripsi_kunci
from .models import PaketAudio
from .tasks import kemas_audiobook

ADA_FFMPEG = shutil.which("ffmpeg") is not None

CONTOH_PLAYLIST = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:10
#EXT-X-MEDIA-SEQUENCE:0
#EXT-X-PLAYLIST-TYPE:VOD
#EXT-X-KEY:METHOD=AES-128,URI="kunci",IV=0x000102030405060708090a0b0c0d0e0f
#EXTINF:10.007800,
seg_00000.ts
#EXTINF:5.008356,
seg_00001.ts
#EXT-X-ENDLIST
"""


def enkripsi_cbc(data, kunci, iv):
    pengisi = padding.PKCS7(128).padder()
    data = pengisi.update(data) + pengisi.finalize()
    enkriptor = Cipher(algorithms.AES(kunci), modes.CBC(iv)).encryptor()
    return enkriptor.update(data) + enkriptor.finalize()


def buat_mp3(detik):
    """MP3 nada sinus untuk pengujian (memakai ffmpeg)."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "uji.mp3"
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
             "-i", f"sine=frequency=440:duration={detik}", "-c:a", "libmp3lame", "-b:a", "128k", str(path)],
            check=True,
        )
        return path.read_bytes()


def isi_folder(prefix):
    try:
        return sorted(default_storage.listdir(prefix)[1])
    except FileNotFoundError:
        return []


@override_settings(FERNET_MASTER_KEY=KUNCI_INDUK_UJI)
class KunciTests(SimpleTestCase):
    def test_enkripsi_dan_dekripsi_kunci(self):
        kunci = bytes(range(16))
        token = enkripsi_kunci(kunci)
        self.assertNotIn(kunci, token)
        self.assertEqual(dekripsi_kunci(token), kunci)
        self.assertEqual(dekripsi_kunci(memoryview(token)), kunci)  # BinaryField dari PostgreSQL

    def test_kunci_harus_16_byte(self):
        with self.assertRaises(ValueError):
            enkripsi_kunci(b"pendek")

    def test_kunci_induk_kosong_atau_tidak_valid(self):
        for nilai in ("", "bukan-kunci-fernet"):
            with self.subTest(nilai=nilai), self.settings(FERNET_MASTER_KEY=nilai):
                with self.assertRaises(ImproperlyConfigured):
                    enkripsi_kunci(bytes(16))

    def test_kunci_induk_lain_tidak_bisa_membuka(self):
        token = enkripsi_kunci(bytes(16))
        with self.settings(FERNET_MASTER_KEY=Fernet.generate_key().decode()), self.assertRaises(InvalidToken):
            dekripsi_kunci(token)


class PlaylistTests(SimpleTestCase):
    def test_membaca_playlist(self):
        self.assertEqual(hls.daftar_segmen(CONTOH_PLAYLIST), ["seg_00000.ts", "seg_00001.ts"])
        self.assertAlmostEqual(hls.durasi_total(CONTOH_PLAYLIST), 15.016156)
        self.assertEqual(hls.iv_playlist(CONTOH_PLAYLIST), bytes(range(16)))
        self.assertIsNone(hls.iv_playlist("#EXTM3U\n"))

    def test_verifikasi_segmen(self):
        kunci, iv = bytes(range(16)), bytes(range(16, 32))
        terenkripsi = enkripsi_cbc((bytes([0x47]) + bytes(187)) * 5, kunci, iv)
        hls.verifikasi_segmen(terenkripsi, kunci, iv)
        for kunci_uji, iv_uji in ((bytes(16), iv), (kunci, bytes(16))):  # kunci salah, IV salah
            with self.subTest(kunci=kunci_uji.hex(), iv=iv_uji.hex()), self.assertRaises(hls.GagalKemas):
                hls.verifikasi_segmen(terenkripsi, kunci_uji, iv_uji)


@override_settings(STORAGES=STORAGES_MEMORI, FERNET_MASTER_KEY=KUNCI_INDUK_UJI)
class AntrikanPengemasanTests(TestCase):
    def setUp(self):
        self.buku = Buku.objects.create(judul="Buku Uji", penulis="Penulis")

    def buat_audiobook(self, nama="a.mp3"):
        return Produk.objects.create(
            buku=self.buku, format=Produk.Format.AUDIOBOOK, harga=60000, berkas=berkas_uji(nama)
        )

    def test_unggah_mp3_membuat_paket_dan_mengantrikan_task(self):
        with mock.patch.object(kemas_audiobook, "delay") as delay, self.captureOnCommitCallbacks(execute=True):
            produk = self.buat_audiobook()
        paket = PaketAudio.objects.get(produk=produk)
        self.assertEqual(paket.status, PaketAudio.Status.MENUNGGU)
        self.assertEqual(paket.berkas_sumber, produk.berkas.name)
        delay.assert_called_once_with(paket.pk)

    def test_hanya_berkas_baru_yang_dikemas_ulang(self):
        with mock.patch.object(kemas_audiobook, "delay"), self.captureOnCommitCallbacks(execute=True):
            produk = self.buat_audiobook()
        with mock.patch.object(kemas_audiobook, "delay") as delay, self.captureOnCommitCallbacks(execute=True):
            produk.harga = 65000
            produk.save()
        delay.assert_not_called()
        with mock.patch.object(kemas_audiobook, "delay") as delay, self.captureOnCommitCallbacks(execute=True):
            produk.berkas = berkas_uji("b.mp3")
            produk.save()
        delay.assert_called_once()

    def test_produk_bukan_audiobook_tidak_dikemas(self):
        with mock.patch.object(kemas_audiobook, "delay") as delay, self.captureOnCommitCallbacks(execute=True):
            Produk.objects.create(buku=self.buku, format=Produk.Format.EBOOK, harga=40000, berkas=berkas_uji("a.pdf"))
            Produk.objects.create(buku=self.buku, format=Produk.Format.CETAK, harga=75000, stok=3)
        delay.assert_not_called()
        self.assertFalse(PaketAudio.objects.exists())

    def test_aksi_admin_proses_ulang(self):
        with mock.patch.object(kemas_audiobook, "delay"), self.captureOnCommitCallbacks(execute=True):
            produk = self.buat_audiobook()
        admin = User.objects.create_superuser(email="admin@example.com", password="x", nama_lengkap="Admin")
        self.client.force_login(admin)
        paket = produk.paket_audio
        with mock.patch.object(kemas_audiobook, "delay") as delay, self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("admin:drm_paketaudio_changelist"),
                {"action": "proses_ulang", "_selected_action": [paket.pk]},
            )
        self.assertEqual(response.status_code, 302)
        delay.assert_called_once_with(paket.pk)


@skipUnless(ADA_FFMPEG, "ffmpeg tidak tersedia")
@override_settings(STORAGES=STORAGES_MEMORI, FERNET_MASTER_KEY=KUNCI_INDUK_UJI)
class KemasAudiobookIntegrasiTests(TestCase):
    """Menjalankan ffmpeg sungguhan, lalu membuktikan hasilnya terenkripsi dan bisa didekripsi."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mp3 = buat_mp3(25)

    def buat_audiobook(self, isi):
        buku = Buku.objects.create(judul="Audiobook Uji", penulis="Penulis")
        with mock.patch.object(kemas_audiobook, "delay"), self.captureOnCommitCallbacks(execute=True):
            return Produk.objects.create(
                buku=buku, format=Produk.Format.AUDIOBOOK, harga=60000, berkas=ContentFile(isi, name="uji.mp3")
            )

    def test_hasil_hls_terenkripsi_dan_bisa_didekripsi_dengan_kunci_tersimpan(self):
        paket = self.buat_audiobook(self.mp3).paket_audio
        self.assertEqual(kemas_audiobook(paket.pk), "siap")
        paket.refresh_from_db()
        self.assertEqual(paket.status, PaketAudio.Status.SIAP)
        self.assertRegex(paket.prefix_hls, r"^hls/[0-9a-f]{32}$")
        self.assertEqual(paket.jumlah_segmen, 3)
        self.assertEqual(paket.durasi_detik, 25)

        playlist = default_storage.open(f"{paket.prefix_hls}/index.m3u8").read().decode()
        self.assertIn('#EXT-X-KEY:METHOD=AES-128,URI="kunci",IV=0x', playlist)
        kunci = dekripsi_kunci(paket.kunci_terenkripsi)
        self.assertNotIn(kunci, bytes(paket.kunci_terenkripsi))  # kunci tidak tersimpan polos
        iv = hls.iv_playlist(playlist)
        for nama in hls.daftar_segmen(playlist):
            terenkripsi = default_storage.open(f"{paket.prefix_hls}/{nama}").read()
            # Di bucket, segmen bukan MPEG-TS polos (byte sinkron 0x47 tidak terlihat) ...
            self.assertNotEqual(terenkripsi[0:188 * 3:188], b"\x47\x47\x47")
            # ... dan menjadi MPEG-TS sah setelah didekripsi dengan kunci serta IV yang benar.
            hls.verifikasi_segmen(terenkripsi, kunci, iv)
        # Hanya playlist dan segmen yang diunggah; berkas kunci tidak ikut.
        self.assertEqual(isi_folder(paket.prefix_hls), ["index.m3u8", "seg_00000.ts", "seg_00001.ts", "seg_00002.ts"])

    def test_proses_ulang_memakai_kunci_baru_dan_menghapus_segmen_lama(self):
        paket = self.buat_audiobook(self.mp3).paket_audio
        kemas_audiobook(paket.pk)
        paket.refresh_from_db()
        prefix_lama, kunci_lama = paket.prefix_hls, dekripsi_kunci(paket.kunci_terenkripsi)
        kemas_audiobook(paket.pk)
        paket.refresh_from_db()
        self.assertNotEqual(paket.prefix_hls, prefix_lama)
        self.assertNotEqual(dekripsi_kunci(paket.kunci_terenkripsi), kunci_lama)
        self.assertEqual(isi_folder(prefix_lama), [])

    def test_berkas_bukan_audio_gagal_dengan_pesan_jelas(self):
        paket = self.buat_audiobook(b"ini bukan audio").paket_audio
        with self.assertLogs("apps.drm.tasks", level="ERROR"):
            self.assertEqual(kemas_audiobook(paket.pk), "gagal")
        paket.refresh_from_db()
        self.assertEqual(paket.status, PaketAudio.Status.GAGAL)
        self.assertIn("ffmpeg gagal", paket.pesan_galat)
        self.assertIsNone(paket.kunci_terenkripsi)

    def test_hapus_produk_ikut_menghapus_segmen(self):
        produk = self.buat_audiobook(self.mp3)
        kemas_audiobook(produk.paket_audio.pk)
        prefix = PaketAudio.objects.get(produk=produk).prefix_hls
        with self.captureOnCommitCallbacks(execute=True):
            produk.delete()
        self.assertEqual(isi_folder(prefix), [])

    def test_perintah_periksa_paket_audio(self):
        paket = self.buat_audiobook(self.mp3).paket_audio
        kemas_audiobook(paket.pk)
        keluaran = StringIO()
        call_command("periksa_paket_audio", stdout=keluaran)
        teks = keluaran.getvalue()
        self.assertIn("apa adanya dari bucket : tidak terbaca", teks)
        self.assertIn("kunci tersimpan  : terbaca", teks)
        self.assertIn("codec_name=aac", teks)
