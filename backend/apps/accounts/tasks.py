import logging

from celery import shared_task
from django.conf import settings

from core.email import kirim_email

from .models import User
from .sandi import tautan_atur_ulang

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30, soft_time_limit=60, time_limit=90)
def kirim_tautan_atur_ulang_sandi(self, pengguna_id):
    """Kirim tautan atur ulang kata sandi ke email pembeli. Token dibuat saat email dikirim."""
    pengguna = User.objects.filter(pk=pengguna_id, is_active=True, role=User.Role.PEMBELI).first()
    if pengguna is None:
        return
    try:
        kirim_email(
            pengguna.email,
            "Atur ulang kata sandi",
            "accounts/email/atur_ulang_sandi",
            {
                "nama": pengguna.nama_lengkap or pengguna.email.partition("@")[0],
                "email": pengguna.email,
                "tautan": tautan_atur_ulang(pengguna),
                "menit": settings.PASSWORD_RESET_TIMEOUT // 60,
            },
        )
    except Exception as exc:
        # Token dan alamat email tidak pernah dicatat di log.
        logger.warning("Email atur ulang sandi untuk pengguna %s gagal (%s); dicoba lagi", pengguna_id, type(exc).__name__)
        raise self.retry(exc=exc) from exc
