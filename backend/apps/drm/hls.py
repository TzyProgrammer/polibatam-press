"""Pengemasan MP3 menjadi HLS terenkripsi AES-128 dengan ffmpeg (RFC 8216).

Kunci (16 byte) dan IV (16 byte) dibuat acak per audiobook. IV ditulis eksplisit di
playlist karena perilaku IV bawaan ffmpeg berbeda antarversi. Setelah ffmpeg selesai,
segmen pertama didekripsi untuk memastikan kunci, IV, dan segmen saling cocok.
"""

import re
import secrets
import subprocess
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

DURASI_SEGMEN = 10  # detik
BITRATE_AUDIO = "128k"
BATAS_WAKTU_FFMPEG = 1800  # detik
# URI kunci di playlist tersimpan hanya penanda; saat disajikan diganti URL endpoint kunci per sesi.
URI_KUNCI = "kunci"
UKURAN_PAKET_TS = 188
BYTE_SINKRON_TS = 0x47

POLA_KUNCI = re.compile(r'^#EXT-X-KEY:METHOD=AES-128,URI="(?P<uri>[^"]*)",IV=0x(?P<iv>[0-9A-Fa-f]{32})\s*$', re.M)
POLA_DURASI = re.compile(r"^#EXTINF:(?P<detik>\d+(?:\.\d+)?)", re.M)


class GagalKemas(Exception):
    """Kesalahan pengemasan. Pesannya aman ditampilkan ke admin (tidak memuat kunci)."""


@dataclass
class HasilKemas:
    kunci: bytes
    iv: bytes
    playlist: str
    segmen: list
    durasi_detik: int


def daftar_segmen(playlist):
    return [baris.strip() for baris in playlist.splitlines() if baris.strip() and not baris.startswith("#")]


def durasi_total(playlist):
    return sum(float(m["detik"]) for m in POLA_DURASI.finditer(playlist))


def iv_playlist(playlist):
    cocok = POLA_KUNCI.search(playlist)
    return bytes.fromhex(cocok["iv"]) if cocok else None


def dekripsi_segmen(data, kunci, iv):
    dekriptor = Cipher(algorithms.AES(kunci), modes.CBC(iv)).decryptor()
    polos = dekriptor.update(data) + dekriptor.finalize()
    pembuka = padding.PKCS7(128).unpadder()
    return pembuka.update(polos) + pembuka.finalize()


def verifikasi_segmen(data, kunci, iv):
    """Segmen harus bisa didekripsi dan hasilnya berupa paket MPEG-TS yang sah."""
    try:
        polos = dekripsi_segmen(data, kunci, iv)
    except ValueError as exc:
        raise GagalKemas("Verifikasi enkripsi gagal: padding tidak valid.") from exc
    jumlah_paket = min(len(polos) // UKURAN_PAKET_TS, 8)
    if jumlah_paket == 0 or any(polos[i * UKURAN_PAKET_TS] != BYTE_SINKRON_TS for i in range(jumlah_paket)):
        raise GagalKemas("Verifikasi enkripsi gagal: hasil dekripsi bukan MPEG-TS.")


def kemas(path_mp3, folder, batas_waktu=BATAS_WAKTU_FFMPEG):
    """Kemas path_mp3 menjadi index.m3u8 + seg_*.ts terenkripsi di folder."""
    folder = Path(folder)
    kunci = secrets.token_bytes(16)
    iv = secrets.token_bytes(16)
    path_kunci = folder / "kunci.bin"
    path_info = folder / "kunci.info"
    path_kunci.write_bytes(kunci)
    path_info.write_text(f"{URI_KUNCI}\n{path_kunci}\n{iv.hex()}\n")
    perintah = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        "-i", str(path_mp3), "-vn", "-c:a", "aac", "-b:a", BITRATE_AUDIO,
        "-f", "hls", "-hls_time", str(DURASI_SEGMEN), "-hls_playlist_type", "vod",
        "-hls_key_info_file", str(path_info),
        "-hls_segment_filename", str(folder / "seg_%05d.ts"),
        str(folder / "index.m3u8"),
    ]
    try:
        hasil = subprocess.run(perintah, capture_output=True, text=True, timeout=batas_waktu)
    except FileNotFoundError as exc:
        raise GagalKemas("ffmpeg tidak ditemukan di worker.") from exc
    except subprocess.TimeoutExpired as exc:
        raise GagalKemas(f"ffmpeg melebihi batas waktu {batas_waktu} detik.") from exc
    finally:
        # Kunci tidak dibiarkan di disk lebih lama dari yang diperlukan ffmpeg.
        path_kunci.unlink(missing_ok=True)
        path_info.unlink(missing_ok=True)
    if hasil.returncode != 0:
        raise GagalKemas("ffmpeg gagal: " + (hasil.stderr or "").strip()[-500:])

    path_playlist = folder / "index.m3u8"
    if not path_playlist.exists():
        raise GagalKemas("ffmpeg tidak menghasilkan playlist.")
    playlist = path_playlist.read_text()
    if iv_playlist(playlist) != iv:
        raise GagalKemas("Playlist tidak memuat tag kunci AES-128 yang diharapkan.")
    segmen = [folder / nama for nama in daftar_segmen(playlist)]
    if not segmen or not all(p.exists() for p in segmen):
        raise GagalKemas("Segmen HLS tidak lengkap.")
    verifikasi_segmen(segmen[0].read_bytes(), kunci, iv)
    return HasilKemas(
        kunci=kunci, iv=iv, playlist=playlist, segmen=segmen, durasi_detik=round(durasi_total(playlist))
    )
