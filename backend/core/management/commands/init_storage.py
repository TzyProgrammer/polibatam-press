from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.s3 import get_s3_client


def aturan_cors():
    """Hanya origin aplikasi (frontend Vite dan Nginx) yang boleh membaca objek dari JavaScript.

    SeaweedFS 4.48 secara bawaan mengizinkan semua origin dan semua metode (-s3.allowedOrigins=*).
    Aturan CORS bucket membatasinya ke origin aplikasi dan metode baca saja. Akses objek tetap
    memerlukan presigned URL; CORS hanya mengatur apakah JavaScript (hls.js, PDF.js) boleh
    membaca respons lintas origin.
    """
    origin = sorted(set(settings.CORS_ALLOWED_ORIGINS) | set(settings.CSRF_TRUSTED_ORIGINS))
    if not origin:
        return None
    return {
        "CORSRules": [
            {
                "AllowedOrigins": origin,
                "AllowedMethods": ["GET", "HEAD"],
                "AllowedHeaders": ["Range"],
                "ExposeHeaders": ["Content-Length", "Content-Range", "ETag"],
                "MaxAgeSeconds": 3000,
            }
        ]
    }


class Command(BaseCommand):
    help = "Membuat bucket S3_BUCKET bila belum ada, lalu memasang aturan CORS bucket."

    def handle(self, *args, **options):
        bucket = settings.AWS_STORAGE_BUCKET_NAME
        client = get_s3_client()
        try:
            client.head_bucket(Bucket=bucket)
            self.stdout.write(f"Bucket '{bucket}' sudah ada.")
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code not in ("404", "NoSuchBucket", "NotFound"):
                raise CommandError(f"Gagal memeriksa bucket: {exc}") from exc
            client.create_bucket(Bucket=bucket)
            self.stdout.write(self.style.SUCCESS(f"Bucket '{bucket}' dibuat."))

        cors = aturan_cors()
        if cors is None:
            self.stdout.write(
                self.style.WARNING("CORS_ALLOWED_ORIGINS dan CSRF_TRUSTED_ORIGINS kosong; aturan CORS tidak dipasang.")
            )
            return
        try:
            client.put_bucket_cors(Bucket=bucket, CORSConfiguration=cors)
        except ClientError as exc:
            raise CommandError(f"Gagal memasang aturan CORS: {exc}") from exc
        daftar = ", ".join(cors["CORSRules"][0]["AllowedOrigins"])
        self.stdout.write(self.style.SUCCESS(f"Aturan CORS bucket dipasang untuk: {daftar}"))
