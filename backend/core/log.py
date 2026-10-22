"""Penyaring log: token sesi streaming pada URL tidak boleh tercatat utuh."""

import logging
import re

POLA_TOKEN_SESI = re.compile(r"(/api/drm/stream/)[^/\s\"?]+")


def samarkan_token_sesi(teks):
    return POLA_TOKEN_SESI.sub(r"\1***", teks)


class SaringTokenSesi(logging.Filter):
    """Mengganti token pada path /api/drm/stream/<token>/... dengan *** sebelum pesan dicatat."""

    def filter(self, record):
        pesan = record.getMessage()
        if "/api/drm/stream/" in pesan:
            record.msg = samarkan_token_sesi(pesan)
            record.args = ()
        return True
