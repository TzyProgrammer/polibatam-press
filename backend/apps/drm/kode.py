import hashlib
import hmac
import re

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

POLA_KODE = re.compile(r"^[0-9A-F]{4}(-[0-9A-F]{4}){3}$")


def buat_kode_watermark(pembeli_id, item_pesanan_id, produk_id):
    """Kode unik watermark ebook: HMAC-SHA256 atas identitas pembelian.

    Kode tidak bisa ditebak tanpa WATERMARK_SECRET, dan dapat dihitung ulang untuk
    membuktikan bahwa kode pada berkas bocor memang diterbitkan sistem ini.
    """
    rahasia = settings.WATERMARK_SECRET
    if not rahasia:
        raise ImproperlyConfigured("WATERMARK_SECRET belum diisi di .env.")
    pesan = f"{pembeli_id}:{item_pesanan_id}:{produk_id}".encode()
    digest = hmac.new(rahasia.encode(), pesan, hashlib.sha256).hexdigest()[:16].upper()
    return "-".join(digest[i:i + 4] for i in range(0, 16, 4))


def kode_cocok(kode, pembeli_id, item_pesanan_id, produk_id):
    """Bandingkan kode dengan hasil hitung ulang secara constant-time."""
    return hmac.compare_digest(kode, buat_kode_watermark(pembeli_id, item_pesanan_id, produk_id))


def hash_token(token):
    """Token sesi streaming hanya disimpan dalam bentuk hash SHA-256."""
    return hashlib.sha256(token.encode()).hexdigest()
