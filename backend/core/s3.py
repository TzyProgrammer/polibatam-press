from functools import lru_cache

import boto3
from django.conf import settings


def get_s3_client(endpoint_url=None):
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url or settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME,
        config=settings.S3_BOTO_CONFIG,
    )


@lru_cache(maxsize=1)
def get_public_s3_client():
    """Klien untuk membuat presigned URL yang dibuka peramban (endpoint publik)."""
    return get_s3_client(endpoint_url=settings.S3_PUBLIC_ENDPOINT_URL)
