from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.s3 import get_s3_client


class Command(BaseCommand):
    help = "Membuat bucket S3_BUCKET bila belum ada."

    def handle(self, *args, **options):
        bucket = settings.AWS_STORAGE_BUCKET_NAME
        client = get_s3_client()
        try:
            client.head_bucket(Bucket=bucket)
            self.stdout.write(f"Bucket '{bucket}' sudah ada.")
            return
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code not in ("404", "NoSuchBucket", "NotFound"):
                raise CommandError(f"Gagal memeriksa bucket: {exc}")
        client.create_bucket(Bucket=bucket)
        self.stdout.write(self.style.SUCCESS(f"Bucket '{bucket}' dibuat."))
