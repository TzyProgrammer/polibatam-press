"""Ubah dan atur ulang kata sandi: tautan email, pemeriksaan token, dan pengakhiran sesi.

Token atur ulang memakai default_token_generator Django (HMAC dari SECRET_KEY, hash kata sandi, waktu masuk
terakhir, dan email). Token tidak disimpan di basis data dan otomatis gugur setelah PASSWORD_RESET_TIMEOUT,
setelah kata sandi berubah (tautan sekali pakai), atau setelah pengguna masuk lagi.

Tautan untuk pembeli berbentuk <FRONTEND_URL>atur-ulang-sandi#uid=...&token=... . Token sengaja diletakkan di
fragmen (#): fragmen tidak pernah dikirim peramban ke server mana pun, jadi tidak tercatat di access log Nginx
maupun header Referer.
"""

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.notifications import layanan as notifikasi

from .models import User


def tautan_atur_ulang(pengguna):
    uid = urlsafe_base64_encode(force_bytes(pengguna.pk))
    token = default_token_generator.make_token(pengguna)
    return f"{settings.FRONTEND_URL}atur-ulang-sandi#uid={uid}&token={token}"


def pengguna_dari_tautan(uid, token):
    """Pembeli pemilik tautan atur ulang, atau None bila tautan tidak valid atau sudah kedaluwarsa."""
    try:
        pk = urlsafe_base64_decode(uid).decode()
        pengguna = User.objects.get(pk=pk, is_active=True, role=User.Role.PEMBELI)
    except (TypeError, ValueError, OverflowError, UnicodeDecodeError, User.DoesNotExist):
        return None
    return pengguna if default_token_generator.check_token(pengguna, token) else None


def akhiri_semua_sesi(pengguna):
    """Blacklist semua refresh token pengguna: perangkat yang masih masuk harus login lagi.

    Access token yang sudah terbit tetap berlaku sampai umurnya habis (ACCESS_TOKEN_LIFETIME, 15 menit).
    """
    belum = OutstandingToken.objects.filter(user=pengguna, blacklistedtoken__isnull=True)
    BlacklistedToken.objects.bulk_create([BlacklistedToken(token=t) for t in belum], ignore_conflicts=True)


def ganti_sandi(pengguna, sandi_baru, cara):
    """Simpan kata sandi baru, keluarkan semua sesi, dan kirim pemberitahuan keamanan (aplikasi + email)."""
    with transaction.atomic():
        pengguna.set_password(sandi_baru)
        pengguna.save(update_fields=["password"])
        akhiri_semua_sesi(pengguna)
        notifikasi.sandi_diubah(pengguna, cara)
