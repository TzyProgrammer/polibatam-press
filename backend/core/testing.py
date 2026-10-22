"""Alat bantu tes bersama."""

from cryptography.fernet import Fernet
from django.core.files.storage import InMemoryStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.encoding import filepath_to_uri


class PenyimpananMemoriUji(InMemoryStorage):
    """Penyimpanan di memori dengan url() bergaya presigned URL, meniru core.storage.PrivateS3Storage."""

    BASIS_URL = "http://s3-uji.invalid/polibatam-press/"

    def url(self, name, parameters=None, expire=None, http_method=None):
        if expire is None:
            expire = 300
        return f"{self.BASIS_URL}{filepath_to_uri(name)}?X-Amz-Expires={expire}&X-Amz-Signature=uji"


# Tes tidak menyentuh SeaweedFS: berkas disimpan di memori.
STORAGES_MEMORI = {
    "default": {"BACKEND": "core.testing.PenyimpananMemoriUji"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

RAHASIA_UJI = "rahasia-khusus-pengujian"
KUNCI_INDUK_UJI = Fernet.generate_key().decode()


def berkas_uji(nama, isi=b"isi uji", content_type="application/octet-stream"):
    return SimpleUploadedFile(nama, isi, content_type=content_type)
