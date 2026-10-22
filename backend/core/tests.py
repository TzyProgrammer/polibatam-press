from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.test import SimpleTestCase

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
