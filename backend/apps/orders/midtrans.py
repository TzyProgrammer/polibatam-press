"""Klien Midtrans: Snap API (membuat transaksi) dan Status API (membaca status transaksi).

Server key hanya dipakai di header Authorization; tidak pernah ditulis ke log, pesan error, atau
respons API. Client key boleh sampai ke peramban karena memang dipakai snap.js.
Dokumentasi: https://docs.midtrans.com (Snap, Get Status API, HTTP Notification).
"""

import base64
import hashlib
import hmac
from urllib.parse import quote

import requests
from django.conf import settings

# Batas waktu (detik) untuk menyambung dan menunggu respons Midtrans.
BATAS_WAKTU = (5, 20)


class GagalMidtrans(Exception):
    """Midtrans tidak bisa dihubungi atau menolak permintaan. Pesannya untuk log, bukan untuk pembeli."""


class BelumDikonfigurasi(GagalMidtrans):
    """MIDTRANS_SERVER_KEY belum diisi di .env."""


def alamat_layanan():
    """(basis Snap, basis API) sesuai MIDTRANS_IS_PRODUCTION."""
    if settings.MIDTRANS_IS_PRODUCTION:
        return "https://app.midtrans.com", "https://api.midtrans.com"
    return "https://app.sandbox.midtrans.com", "https://api.sandbox.midtrans.com"


def url_snap_js():
    return f"{alamat_layanan()[0]}/snap/snap.js"


def _header():
    kunci = settings.MIDTRANS_SERVER_KEY
    if not kunci:
        raise BelumDikonfigurasi("MIDTRANS_SERVER_KEY belum diisi di .env.")
    # Basic auth: server key sebagai username, password kosong.
    kredensial = base64.b64encode(f"{kunci}:".encode()).decode()
    return {
        "Authorization": f"Basic {kredensial}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _isi_json(respons):
    try:
        data = respons.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _pesan_error(data):
    pesan = data.get("error_messages") or data.get("status_message") or "tanpa keterangan"
    if isinstance(pesan, list):
        pesan = "; ".join(str(p) for p in pesan)
    return str(pesan)[:300]


def buat_transaksi_snap(payload):
    """Membuat transaksi Snap. Mengembalikan {"token": ..., "redirect_url": ...}."""
    url = f"{alamat_layanan()[0]}/snap/v1/transactions"
    try:
        respons = requests.post(url, json=payload, headers=_header(), timeout=BATAS_WAKTU)
    except requests.RequestException as exc:
        raise GagalMidtrans(f"Snap API tidak bisa dihubungi ({exc.__class__.__name__}).") from exc
    data = _isi_json(respons)
    if respons.status_code not in (200, 201) or not data.get("token") or not data.get("redirect_url"):
        raise GagalMidtrans(f"Snap API menolak permintaan (HTTP {respons.status_code}): {_pesan_error(data)}")
    return {"token": data["token"], "redirect_url": data["redirect_url"]}


def status_transaksi(order_id):
    """Status transaksi dari Get Status API.

    Mengembalikan None bila Midtrans belum mengenal order_id, yaitu pembeli belum memilih metode
    bayar di Snap.
    """
    url = f"{alamat_layanan()[1]}/v2/{quote(order_id, safe='')}/status"
    try:
        respons = requests.get(url, headers=_header(), timeout=BATAS_WAKTU)
    except requests.RequestException as exc:
        raise GagalMidtrans(f"Status API tidak bisa dihubungi ({exc.__class__.__name__}).") from exc
    data = _isi_json(respons)
    kode = str(data.get("status_code") or respons.status_code)
    if respons.status_code == 404 or kode == "404":
        return None
    if respons.status_code >= 400 or not data.get("transaction_status"):
        raise GagalMidtrans(
            f"Status API menolak permintaan (HTTP {respons.status_code}, kode {kode}): {_pesan_error(data)}"
        )
    return data


def tanda_tangan(order_id, status_code, gross_amount):
    """signature_key = SHA512(order_id + status_code + gross_amount + server key)."""
    teks = f"{order_id}{status_code}{gross_amount}{settings.MIDTRANS_SERVER_KEY}"
    return hashlib.sha512(teks.encode()).hexdigest()


def tanda_tangan_valid(data):
    """True bila notifikasi benar-benar ditandatangani dengan server key milik toko ini."""
    if not settings.MIDTRANS_SERVER_KEY or not isinstance(data, dict):
        # Tanpa server key, tanda tangan bisa dibuat siapa saja; semua notifikasi ditolak.
        return False
    bagian = [data.get("order_id"), data.get("status_code"), data.get("gross_amount")]
    diterima = data.get("signature_key")
    if not all(isinstance(b, str) and b for b in bagian) or not isinstance(diterima, str):
        return False
    return hmac.compare_digest(tanda_tangan(*bagian).encode(), diterima.strip().lower().encode())
