"""Sesi streaming bertoken dan penulisan ulang playlist HLS per sesi (Tahap C)."""

import ipaddress
import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.files.storage import default_storage
from django.utils import timezone

from .kode import hash_token
from .models import SesiStreaming

# Segmen terenkripsi tidak berguna tanpa kunci, jadi presigned URL-nya boleh berumur
# sepanjang durasi audio + cadangan, dibatasi maksimal 6 jam.
CADANGAN_UMUR_SEGMEN = 30 * 60
BATAS_UMUR_SEGMEN = 6 * 60 * 60
POLA_URI_KUNCI = re.compile(r'URI="[^"]*"')


def alamat_ip(request):
    """IP klien; Nginx meneruskannya lewat X-Real-IP. Nilai tidak valid diabaikan."""
    for nilai in (request.META.get("HTTP_X_REAL_IP"), request.META.get("REMOTE_ADDR")):
        try:
            return str(ipaddress.ip_address((nilai or "").strip()))
        except ValueError:
            continue
    return None


def buat_sesi(pembeli, paket, request):
    """Membuat sesi baru dan mencabut sesi aktif lain milik pembeli untuk audiobook yang sama.

    Mengembalikan (sesi, token). Token asli hanya dikirim sekali ke pembeli; basis data
    hanya menyimpan hash-nya.
    """
    token = secrets.token_urlsafe(32)
    sekarang = timezone.now()
    SesiStreaming.objects.filter(pembeli=pembeli, paket=paket, dicabut=False, kedaluwarsa__gt=sekarang).update(
        dicabut=True
    )
    sesi = SesiStreaming.objects.create(
        pembeli=pembeli,
        paket=paket,
        token_hash=hash_token(token),
        kedaluwarsa=sekarang + timedelta(minutes=settings.STREAMING_SESSION_MINUTES),
        alamat_ip=alamat_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
    )
    return sesi, token


def umur_segmen(paket):
    minimal = settings.STREAMING_SESSION_MINUTES * 60
    return max(minimal, min(BATAS_UMUR_SEGMEN, paket.durasi_detik + CADANGAN_UMUR_SEGMEN))


def tulis_ulang_playlist(paket, url_kunci):
    """Playlist untuk satu sesi.

    URI kunci diarahkan ke endpoint kunci milik sesi, nama segmen diganti presigned URL.
    Playlist asli di bucket tidak berubah.
    """
    with default_storage.open(f"{paket.prefix_hls}/index.m3u8") as berkas:
        asli = berkas.read().decode()
    umur = umur_segmen(paket)
    hasil = []
    for baris in asli.splitlines():
        if baris.startswith("#EXT-X-KEY:"):
            baris = POLA_URI_KUNCI.sub(lambda _: f'URI="{url_kunci}"', baris, count=1)
        elif baris.strip() and not baris.startswith("#"):
            baris = default_storage.url(f"{paket.prefix_hls}/{baris.strip()}", expire=umur)
        hasil.append(baris)
    return "\n".join(hasil) + "\n"
