import logging
from io import StringIO
from unittest import mock
from urllib.parse import parse_qs, urlparse

from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.http import Http404
from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import Throttled

from .exceptions import penangan_exception
from .storage import PrivateS3Storage


class PrivateS3StorageTests(SimpleTestCase):
    def test_url_berupa_presigned_url_lewat_endpoint_publik(self):
        url = PrivateS3Storage().url("sampul/contoh.jpg", expire=120)
        parsed = urlparse(url)
        publik = urlparse(settings.S3_PUBLIC_ENDPOINT_URL)
        self.assertEqual(parsed.netloc, publik.netloc)
        self.assertEqual(parsed.path, f"/{settings.AWS_STORAGE_BUCKET_NAME}/sampul/contoh.jpg")
        query = parse_qs(parsed.query)
        self.assertIn("X-Amz-Signature", query)
        self.assertEqual(query["X-Amz-Expires"], ["120"])

    def test_umur_bawaan_presigned_url_lima_menit(self):
        url = PrivateS3Storage().url("sampul/contoh.jpg")
        self.assertEqual(parse_qs(urlparse(url).query)["X-Amz-Expires"], ["300"])


@override_settings(
    CORS_ALLOWED_ORIGINS=["http://localhost:5173"],
    CSRF_TRUSTED_ORIGINS=["http://localhost:8080", "http://localhost:5173"],
)
class InitStorageTests(SimpleTestCase):
    def jalankan(self, client):
        keluaran = StringIO()
        with mock.patch("core.management.commands.init_storage.get_s3_client", return_value=client):
            call_command("init_storage", stdout=keluaran)
        return keluaran.getvalue()

    def test_bucket_baru_dibuat_dan_cors_dipasang(self):
        client = mock.Mock()
        client.head_bucket.side_effect = ClientError({"Error": {"Code": "404"}}, "HeadBucket")
        teks = self.jalankan(client)
        client.create_bucket.assert_called_once_with(Bucket=settings.AWS_STORAGE_BUCKET_NAME)
        aturan = client.put_bucket_cors.call_args.kwargs["CORSConfiguration"]["CORSRules"][0]
        # Origin digabung tanpa duplikat; hanya metode baca.
        self.assertEqual(aturan["AllowedOrigins"], ["http://localhost:5173", "http://localhost:8080"])
        self.assertEqual(aturan["AllowedMethods"], ["GET", "HEAD"])
        self.assertIn("dibuat", teks)
        self.assertIn("Aturan CORS bucket dipasang", teks)

    def test_bucket_sudah_ada_tetap_memasang_cors(self):
        client = mock.Mock()
        teks = self.jalankan(client)
        client.create_bucket.assert_not_called()
        client.put_bucket_cors.assert_called_once()
        self.assertIn("sudah ada", teks)

    def test_tanpa_origin_cors_tidak_dipasang(self):
        client = mock.Mock()
        with self.settings(CORS_ALLOWED_ORIGINS=[], CSRF_TRUSTED_ORIGINS=[]):
            teks = self.jalankan(client)
        client.put_bucket_cors.assert_not_called()
        self.assertIn("tidak dipasang", teks)

    def test_galat_lain_saat_memeriksa_bucket(self):
        client = mock.Mock()
        client.head_bucket.side_effect = ClientError({"Error": {"Code": "403"}}, "HeadBucket")
        with self.assertRaises(CommandError):
            self.jalankan(client)
        client.create_bucket.assert_not_called()


class PenanganExceptionTests(SimpleTestCase):
    def test_pesan_404_dari_get_object_or_404_diseragamkan(self):
        response = penangan_exception(Http404("No Produk matches the given query."), {})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"detail": "Data tidak ditemukan."})

    def test_pesan_throttle(self):
        response = penangan_exception(Throttled(wait=12.2), {})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data, {"detail": "Terlalu banyak permintaan. Coba lagi dalam 13 detik."})

    def test_exception_lain_tidak_ditangani(self):
        self.assertIsNone(penangan_exception(ValueError("bukan exception API"), {}))


class SaringTokenSesiTests(SimpleTestCase):
    def test_token_sesi_disamarkan_di_log_django(self):
        for nama in ("django.request", "django.server"):
            with self.subTest(logger=nama), self.assertLogs(nama, level="WARNING") as log:
                logging.getLogger(nama).warning('"%s" %s', "GET /api/drm/stream/TokenRahasia_123/kunci HTTP/1.1", 401)
            self.assertEqual(log.records[0].getMessage(), '"GET /api/drm/stream/***/kunci HTTP/1.1" 401')

    def test_pesan_lain_tidak_berubah(self):
        with self.assertLogs("django.request", level="WARNING") as log:
            logging.getLogger("django.request").warning("%s: %s", "Not Found", "/api/auth/profil/")
        self.assertEqual(log.records[0].getMessage(), "Not Found: /api/auth/profil/")
