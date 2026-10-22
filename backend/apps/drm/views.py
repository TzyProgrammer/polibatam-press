from datetime import timedelta

from django.conf import settings
from django.core.files.storage import default_storage
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Produk

from .kode import hash_token
from .kunci import dekripsi_kunci
from .layanan import siapkan_salinan_ebook
from .models import HakAkses, LogAksesKunci, PaketAudio, SalinanEbook, SesiStreaming
from .streaming import alamat_ip, buat_sesi, tulis_ulang_playlist

TANPA_CACHE = {"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache"}

# Alasan penolakan playlist/kunci → (kode HTTP, pesan untuk pembeli). Alasan dicatat di LogAksesKunci.
PENOLAKAN = {
    "tanpa login": (status.HTTP_401_UNAUTHORIZED, "Login diperlukan."),
    "JWT tidak valid": (status.HTTP_401_UNAUTHORIZED, "Token login tidak valid atau sudah kedaluwarsa."),
    "token tidak dikenal": (status.HTTP_404_NOT_FOUND, "Sesi streaming tidak ditemukan."),
    "bukan pemilik sesi": (status.HTTP_403_FORBIDDEN, "Sesi ini bukan milik Anda."),
    "sesi dicabut": (status.HTTP_410_GONE, "Sesi streaming sudah dicabut. Mulai ulang pemutaran."),
    "sesi kedaluwarsa": (status.HTTP_410_GONE, "Sesi streaming sudah kedaluwarsa. Mulai ulang pemutaran."),
    "hak akses dicabut": (status.HTTP_403_FORBIDDEN, "Hak akses Anda ke audiobook ini sudah dicabut."),
    "paket belum siap": (status.HTTP_409_CONFLICT, "Audiobook sedang diproses ulang. Coba lagi beberapa saat."),
}


class SesiStreamingBaruView(APIView):
    """POST /api/drm/audiobook/<produk_id>/sesi/ — membuka sesi pemutaran bagi pemilik audiobook."""

    throttle_scope = "sesi_streaming"

    def post(self, request, produk_id):
        produk = Produk.objects.filter(pk=produk_id, format=Produk.Format.AUDIOBOOK).first()
        if produk is None:
            return Response({"detail": "Audiobook tidak ditemukan."}, status=status.HTTP_404_NOT_FOUND)
        if not HakAkses.objects.filter(pembeli=request.user, produk=produk, aktif=True).exists():
            return Response(
                {"detail": "Anda tidak memiliki hak akses ke audiobook ini."}, status=status.HTTP_403_FORBIDDEN
            )
        paket = PaketAudio.objects.filter(produk=produk).first()
        if paket is None or paket.status != PaketAudio.Status.SIAP:
            return Response(
                {"detail": "Audiobook belum siap diputar. Coba lagi beberapa saat."}, status=status.HTTP_409_CONFLICT
            )
        sesi, token = buat_sesi(request.user, paket, request)
        return Response(
            {
                "playlist": request.build_absolute_uri(reverse("drm-playlist", args=[token])),
                "kedaluwarsa": sesi.kedaluwarsa,
            },
            status=status.HTTP_201_CREATED,
            headers=TANPA_CACHE,
        )


class SesiTokenMixin:
    """Validasi bersama untuk playlist dan kunci.

    Autentikasi tetap JWT, tetapi diperiksa di sini (bukan oleh izin DRF) agar setiap
    penolakan, termasuk tanpa login, bisa dicatat di LogAksesKunci.
    """

    permission_classes = [AllowAny]
    jwt_tidak_valid = False

    def perform_authentication(self, request):
        try:
            super().perform_authentication(request)
        except AuthenticationFailed:
            # JWT rusak atau kedaluwarsa: DRF sudah menetapkan pengguna anonim; penolakan 401
            # beserta catatan lognya diberikan oleh periksa_sesi.
            self.jwt_tidak_valid = True

    def alasan_penolakan(self, sesi, pengguna):
        if pengguna is None:
            return "JWT tidak valid" if self.jwt_tidak_valid else "tanpa login"
        if sesi is None:
            return "token tidak dikenal"
        if sesi.pembeli_id != pengguna.pk:
            return "bukan pemilik sesi"
        if sesi.dicabut:
            return "sesi dicabut"
        if sesi.kedaluwarsa <= timezone.now():
            return "sesi kedaluwarsa"
        if not HakAkses.objects.filter(pembeli=pengguna, produk_id=sesi.paket.produk_id, aktif=True).exists():
            return "hak akses dicabut"
        if sesi.paket.status != PaketAudio.Status.SIAP:
            return "paket belum siap"
        return None

    def periksa_sesi(self, request, token, catat_log):
        """Mengembalikan (sesi, None) bila permintaan sah, atau (None, respons penolakan)."""
        sesi = SesiStreaming.objects.select_related("paket").filter(token_hash=hash_token(token)).first()
        pengguna = request.user if request.user.is_authenticated else None
        alasan = self.alasan_penolakan(sesi, pengguna)
        if alasan is None:
            return sesi, None
        if catat_log:
            LogAksesKunci.objects.create(
                sesi=sesi,
                pengguna=pengguna,
                paket=sesi.paket if sesi else None,
                hasil=LogAksesKunci.Hasil.DITOLAK,
                alasan=alasan,
                alamat_ip=alamat_ip(request),
            )
        kode, pesan = PENOLAKAN[alasan]
        headers = dict(TANPA_CACHE)
        if kode == status.HTTP_401_UNAUTHORIZED:
            headers["WWW-Authenticate"] = 'Bearer realm="api"'
        return None, Response({"detail": pesan}, status=kode, headers=headers)


class PlaylistView(SesiTokenMixin, APIView):
    """GET /api/drm/stream/<token>/playlist.m3u8 — playlist HLS milik satu sesi."""

    def get(self, request, token):
        sesi, penolakan = self.periksa_sesi(request, token, catat_log=False)
        if penolakan:
            return penolakan
        url_kunci = request.build_absolute_uri(reverse("drm-kunci", args=[token]))
        return HttpResponse(
            tulis_ulang_playlist(sesi.paket, url_kunci),
            content_type="application/vnd.apple.mpegurl",
            headers=TANPA_CACHE,
        )


class KunciView(SesiTokenMixin, APIView):
    """GET /api/drm/stream/<token>/kunci — 16 byte kunci AES-128, hanya untuk pemilik sesi yang sah."""

    throttle_scope = "kunci"

    def get(self, request, token):
        sesi, penolakan = self.periksa_sesi(request, token, catat_log=True)
        if penolakan:
            return penolakan
        kunci = dekripsi_kunci(sesi.paket.kunci_terenkripsi)
        LogAksesKunci.objects.create(
            sesi=sesi,
            pengguna=request.user,
            paket=sesi.paket,
            hasil=LogAksesKunci.Hasil.DIIZINKAN,
            alamat_ip=alamat_ip(request),
        )
        return HttpResponse(kunci, content_type="application/octet-stream", headers=TANPA_CACHE)


class SalinanEbookView(APIView):
    """GET /api/drm/ebook/<produk_id>/ — presigned URL 5 menit ke salinan ber-watermark milik pembeli.

    Berkas asli tidak pernah diberikan; pembeli hanya menerima salinannya sendiri.
    """

    throttle_scope = "ebook"

    def get(self, request, produk_id):
        produk = Produk.objects.select_related("buku").filter(pk=produk_id, format=Produk.Format.EBOOK).first()
        if produk is None:
            return Response({"detail": "Ebook tidak ditemukan."}, status=status.HTTP_404_NOT_FOUND)
        hak = HakAkses.objects.filter(pembeli=request.user, produk=produk, aktif=True).first()
        if hak is None:
            return Response({"detail": "Anda tidak memiliki hak akses ke ebook ini."}, status=status.HTTP_403_FORBIDDEN)
        # Bila salinan belum pernah dibuat (misalnya worker sempat mati), siapkan sekarang.
        salinan = SalinanEbook.objects.filter(hak_akses=hak).first() or siapkan_salinan_ebook(hak)
        if salinan.status != SalinanEbook.Status.SIAP or not salinan.berkas:
            pesan = (
                "Salinan ebook gagal disiapkan. Hubungi admin."
                if salinan.status == SalinanEbook.Status.GAGAL
                else "Salinan ebook sedang disiapkan. Coba lagi beberapa saat."
            )
            return Response(
                {"detail": pesan, "status": salinan.status}, status=status.HTTP_409_CONFLICT, headers=TANPA_CACHE
            )
        umur = settings.AWS_QUERYSTRING_EXPIRE
        nama = f"{slugify(produk.buku.judul) or 'ebook'}.pdf"
        url = default_storage.url(
            salinan.berkas.name,
            parameters={
                "ResponseContentDisposition": f'inline; filename="{nama}"',
                "ResponseCacheControl": "private, no-store",
            },
            expire=umur,
        )
        return Response(
            {"url": url, "kedaluwarsa": timezone.now() + timedelta(seconds=umur)}, headers=TANPA_CACHE
        )


def uji_pemutar(request):
    """Halaman uji pemutar HLS (hanya saat DEBUG) untuk demonstrasi sebelum frontend Vue tersedia."""
    if not settings.DEBUG:
        raise Http404
    return render(request, "drm/uji_pemutar.html")
