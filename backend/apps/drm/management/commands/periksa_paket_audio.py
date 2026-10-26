"""Bukti uji enkripsi/dekripsi audiobook untuk laporan.

Untuk setiap paket audio yang siap: segmen pertama di bucket diuji dengan ffprobe
(harus gagal karena terenkripsi), lalu didekripsi dengan kunci tersimpan dan diuji
lagi (harus terbaca sebagai audio AAC). Kunci tidak pernah dicetak.
"""

import subprocess
import tempfile
from pathlib import Path

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from apps.drm import hls
from apps.drm.kunci import dekripsi_kunci
from apps.drm.models import PaketAudio


def ffprobe(path):
    """Apakah berkas terbaca sebagai segmen HLS (MPEG-TS) yang berisi audio.

    Yang dihitung terbaca hanya stream audio: tanpa batasan ini, data acak seperti segmen terenkripsi
    sesekali (sekitar 1-3% percobaan) salah dikenali ffprobe sebagai format lain, misalnya subtitle teks.
    """
    hasil = subprocess.run(
        ["ffprobe", "-v", "error", "-f", "mpegts",
         "-show_entries", "stream=codec_type,codec_name,sample_rate,channels:format=duration",
         "-of", "default=noprint_wrappers=1", str(path)],
        capture_output=True, text=True, timeout=60,
    )

    def baris(teks):
        return [b.strip() for b in teks.replace(f"{path}: ", "").splitlines() if b.strip()]

    data = baris(hasil.stdout)
    terbaca = hasil.returncode == 0 and "codec_type=audio" in data
    if terbaca:
        keluaran = ", ".join(b for b in dict.fromkeys(data) if not b.startswith("codec_type="))  # buang baris ganda
    else:
        keluaran = ", ".join(dict.fromkeys(baris(hasil.stderr))) or "tidak ada stream audio yang dikenali"
    return terbaca, keluaran


class Command(BaseCommand):
    help = "Menguji bahwa segmen audiobook terenkripsi dan hanya terbaca setelah didekripsi dengan kunci yang benar."

    def add_arguments(self, parser):
        parser.add_argument("produk_id", nargs="*", type=int, help="ID produk audiobook (kosong = semua yang siap).")

    def handle(self, *args, **options):
        paket_list = PaketAudio.objects.select_related("produk__buku").filter(status=PaketAudio.Status.SIAP)
        if options["produk_id"]:
            paket_list = paket_list.filter(produk_id__in=options["produk_id"])
        if not paket_list:
            self.stdout.write(self.style.WARNING("Tidak ada paket audio berstatus siap."))
            return
        for paket in paket_list:
            self.stdout.write(f"\n{paket.produk} — {paket.jumlah_segmen} segmen, {paket.durasi_detik} detik")
            playlist = default_storage.open(f"{paket.prefix_hls}/index.m3u8").read().decode()
            nama_segmen = hls.daftar_segmen(playlist)[0]
            terenkripsi = default_storage.open(f"{paket.prefix_hls}/{nama_segmen}").read()
            kunci = dekripsi_kunci(paket.kunci_terenkripsi)
            iv = hls.iv_playlist(playlist)
            with tempfile.TemporaryDirectory() as tmp:
                path_enkripsi = Path(tmp) / "terenkripsi.ts"
                path_dekripsi = Path(tmp) / "didekripsi.ts"
                path_enkripsi.write_bytes(terenkripsi)
                path_dekripsi.write_bytes(hls.dekripsi_segmen(terenkripsi, kunci, iv))
                terbaca_enkripsi, info_enkripsi = ffprobe(path_enkripsi)
                terbaca_dekripsi, info_dekripsi = ffprobe(path_dekripsi)
            gaya_1 = self.style.ERROR if terbaca_enkripsi else self.style.SUCCESS
            gaya_2 = self.style.SUCCESS if terbaca_dekripsi else self.style.ERROR
            self.stdout.write(gaya_1(f"  1. {nama_segmen} apa adanya dari bucket : "
                                     f"{'TERBACA (tidak aman!)' if terbaca_enkripsi else 'tidak terbaca'} — {info_enkripsi}"))
            self.stdout.write(gaya_2(f"  2. Setelah didekripsi kunci tersimpan  : "
                                     f"{'terbaca' if terbaca_dekripsi else 'TIDAK terbaca'} — {info_dekripsi}"))
