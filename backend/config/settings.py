import os
from datetime import timedelta
from pathlib import Path

from botocore.config import Config

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()]

INSTALLED_APPS = [
    "config.apps.AdminPolibatamConfig",  # django.contrib.admin dengan situs admin kustom (config/admin.py)
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "storages",
    "core",
    "apps.accounts",
    "apps.catalog",
    "apps.orders",
    "apps.drm",
    "apps.isbn",
    "apps.notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # templates/ di backend dipakai untuk mengganti template admin secara global (submit_line.html)
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["POSTGRES_DB"],
        "USER": os.environ["POSTGRES_USER"],
        "PASSWORD": os.environ["POSTGRES_PASSWORD"],
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "id"
TIME_ZONE = "Asia/Jakarta"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

def env_list(name):
    return [v.strip() for v in os.environ.get(name, "").split(",") if v.strip()]


CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "EXCEPTION_HANDLER": "core.exceptions.penangan_exception",
    # Pembatasan laju hanya untuk view yang memiliki throttle_scope.
    # Penghitung disimpan di cache bawaan Django (memori proses runserver).
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "login": "10/min",
        "registrasi": "5/min",
        "refresh": "30/min",
        "sesi_streaming": "20/min",
        "kunci": "60/min",
        "ebook": "30/min",
    },
    # Satu proxy (Nginx) di depan Django: IP klien diambil dari entri terakhir X-Forwarded-For.
    "NUM_PROXIES": 1,
    # Parameter ?format= dipakai filter katalog (cetak/ebook/audiobook), bukan pemilih format respons DRF.
    "URL_FORMAT_OVERRIDE": None,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    # Setiap refresh menghasilkan refresh token baru; yang lama di-blacklist (juga saat logout).
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

# Celery (Valkey kompatibel dengan protokol Redis)
CELERY_BROKER_URL = os.environ["CELERY_BROKER_URL"]
CELERY_RESULT_BACKEND = os.environ["CELERY_RESULT_BACKEND"]
CELERY_TIMEZONE = TIME_ZONE

# Object storage S3 (SeaweedFS)
AWS_ACCESS_KEY_ID = os.environ["S3_ACCESS_KEY"]
AWS_SECRET_ACCESS_KEY = os.environ["S3_SECRET_KEY"]
AWS_STORAGE_BUCKET_NAME = os.environ["S3_BUCKET"]
AWS_S3_ENDPOINT_URL = os.environ["S3_ENDPOINT_URL"]
AWS_S3_REGION_NAME = "us-east-1"
AWS_S3_ADDRESSING_STYLE = "path"
AWS_S3_SIGNATURE_VERSION = "s3v4"
S3_PUBLIC_ENDPOINT_URL = os.environ.get("S3_PUBLIC_ENDPOINT_URL", AWS_S3_ENDPOINT_URL)
# Umur bawaan presigned URL (detik). Pemanggil boleh memberi expire sendiri bila perlu.
AWS_QUERYSTRING_EXPIRE = 300

S3_BOTO_CONFIG = Config(
    signature_version=AWS_S3_SIGNATURE_VERSION,
    s3={"addressing_style": AWS_S3_ADDRESSING_STYLE},
    connect_timeout=3,
    read_timeout=5,
    retries={"max_attempts": 1},
)

STORAGES = {
    # Bucket privat; URL berkas = presigned URL lewat S3_PUBLIC_ENDPOINT_URL (lihat core/storage.py)
    "default": {"BACKEND": "core.storage.PrivateS3Storage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Keamanan konten (DRM)
# Kunci induk Fernet untuk mengenkripsi kunci AES-128 tiap audiobook sebelum disimpan di basis data
FERNET_MASTER_KEY = os.environ.get("FERNET_MASTER_KEY", "")
# Rahasia HMAC untuk kode unik watermark ebook; terpisah dari SECRET_KEY dan FERNET_MASTER_KEY
WATERMARK_SECRET = os.environ.get("WATERMARK_SECRET", "")
# Umur sesi streaming audiobook (menit)
STREAMING_SESSION_MINUTES = int(os.environ.get("STREAMING_SESSION_MINUTES", "10"))
