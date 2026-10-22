"""Alat bantu tes bersama."""

from django.core.files.uploadedfile import SimpleUploadedFile

# Tes tidak menyentuh SeaweedFS: berkas disimpan di memori.
STORAGES_MEMORI = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

RAHASIA_UJI = "rahasia-khusus-pengujian"


def berkas_uji(nama, isi=b"isi uji", content_type="application/octet-stream"):
    return SimpleUploadedFile(nama, isi, content_type=content_type)
