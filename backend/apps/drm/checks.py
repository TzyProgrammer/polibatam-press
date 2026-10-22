from django.conf import settings
from django.core.checks import Warning, register
from django.core.exceptions import ImproperlyConfigured

from .kunci import periksa_konfigurasi


@register()
def periksa_rahasia_drm(app_configs, **kwargs):
    """Peringatan saat startup bila rahasia DRM di .env belum diisi atau tidak valid."""
    peringatan = []
    try:
        periksa_konfigurasi()
    except ImproperlyConfigured as exc:
        peringatan.append(
            Warning(str(exc), hint="Audiobook tidak bisa dikemas sampai FERNET_MASTER_KEY valid.", id="drm.W001")
        )
    if not settings.WATERMARK_SECRET:
        peringatan.append(
            Warning(
                "WATERMARK_SECRET belum diisi di .env.",
                hint="Salinan ebook ber-watermark tidak bisa dibuat sampai rahasia ini diisi.",
                id="drm.W002",
            )
        )
    return peringatan
