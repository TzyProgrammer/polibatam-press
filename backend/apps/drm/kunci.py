"""Penyimpanan kunci AES-128 audiobook: dienkripsi Fernet dengan FERNET_MASTER_KEY sebelum masuk basis data."""

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

PANJANG_KUNCI = 16  # AES-128


def _fernet():
    kunci_induk = settings.FERNET_MASTER_KEY
    if not kunci_induk:
        raise ImproperlyConfigured("FERNET_MASTER_KEY belum diisi di .env.")
    try:
        return Fernet(kunci_induk)
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured("FERNET_MASTER_KEY tidak valid (harus 32 byte base64 URL-safe).") from exc


def periksa_konfigurasi():
    """Gagal lebih awal bila kunci induk belum siap, sebelum pekerjaan berat dimulai."""
    _fernet()


def enkripsi_kunci(kunci):
    if len(kunci) != PANJANG_KUNCI:
        raise ValueError("Kunci AES-128 harus 16 byte.")
    return _fernet().encrypt(bytes(kunci))


def dekripsi_kunci(token):
    kunci = _fernet().decrypt(bytes(token))
    if len(kunci) != PANJANG_KUNCI:
        raise ValueError("Kunci hasil dekripsi bukan 16 byte.")
    return kunci
