"""Penanganan exception DRF agar pesan error API konsisten berbahasa Indonesia.

Beberapa pesan bawaan belum diterjemahkan atau tidak seragam: token simplejwt
("Token is invalid", "Token is expired"), get_object_or_404 ("No Produk matches the
given query."), serta sebagian pesan DRF (metode tidak diizinkan, waktu tunggu throttle).
"""

import math

from django.http import Http404
from rest_framework.exceptions import MethodNotAllowed, Throttled
from rest_framework.views import exception_handler
from rest_framework_simplejwt.exceptions import InvalidToken

PESAN_TOKEN_TIDAK_VALID = "Token tidak valid atau sudah kedaluwarsa."


def penangan_exception(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None
    if isinstance(exc, Http404):
        response.data = {"detail": "Data tidak ditemukan."}
    elif isinstance(exc, InvalidToken):
        # Kode "token_not_valid" dipertahankan agar frontend tahu kapan harus refresh atau login ulang.
        response.data = {"detail": PESAN_TOKEN_TIDAK_VALID, "code": "token_not_valid"}
    elif isinstance(exc, MethodNotAllowed):
        response.data = {"detail": f"Metode {context['request'].method} tidak diizinkan."}
    elif isinstance(exc, Throttled):
        pesan = "Terlalu banyak permintaan."
        if exc.wait is not None:
            pesan += f" Coba lagi dalam {math.ceil(exc.wait)} detik."
        response.data = {"detail": pesan}
    return response
