import redis
from botocore.exceptions import ClientError
from django.conf import settings
from django.db import connection
from django.http import JsonResponse

from .s3 import get_s3_client


def _check_db():
    with connection.cursor() as cur:
        cur.execute("SELECT 1")


def _check_broker():
    redis.Redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=3, socket_timeout=3).ping()


def _check_storage():
    get_s3_client().head_bucket(Bucket=settings.AWS_STORAGE_BUCKET_NAME)


def health(request):
    checks = {"db": _check_db, "broker": _check_broker, "storage": _check_storage}
    result = {}
    for name, fn in checks.items():
        try:
            fn()
            result[name] = "ok"
        except ClientError as exc:
            result[name] = f"error: {exc.response.get('Error', {}).get('Code', 'ClientError')}"
        except Exception as exc:
            result[name] = f"error: {type(exc).__name__}"
    status = 200 if all(v == "ok" for v in result.values()) else 503
    return JsonResponse(result, status=status)
