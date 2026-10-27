import logging

from celery import shared_task

from core.email import kirim_email, tautan_frontend

from .models import Notifikasi

logger = logging.getLogger(__name__)


def label_tautan(tautan):
    if tautan.startswith("/lupa-sandi"):
        return "Atur ulang kata sandi"
    return "Lihat detail"


@shared_task(bind=True, max_retries=3, default_retry_delay=60, soft_time_limit=60, time_limit=90)
def kirim_email_notifikasi(self, notifikasi_id):
    """Kirim salinan satu notifikasi ke email penerimanya (sekali saja; diulang bila SMTP gagal)."""
    notifikasi = Notifikasi.objects.select_related("penerima").filter(pk=notifikasi_id).first()
    if notifikasi is None or notifikasi.email_terkirim:
        return
    penerima = notifikasi.penerima
    if not penerima.is_active or not penerima.email:
        return
    tautan = tautan_frontend(notifikasi.tautan) if notifikasi.tautan else ""
    try:
        kirim_email(
            penerima.email,
            notifikasi.judul,
            "notifications/email/notifikasi",
            {
                "nama": penerima.nama_lengkap or penerima.email.partition("@")[0],
                "judul": notifikasi.judul,
                "pesan": notifikasi.pesan,
                "kategori": notifikasi.get_kategori_display(),
                "tautan": tautan,
                "label": label_tautan(notifikasi.tautan),
            },
        )
    except Exception as exc:
        # Alamat email tidak dicatat di log; cukup nomor notifikasi dan jenis galat.
        logger.warning("Email notifikasi %s gagal dikirim (%s); dicoba lagi", notifikasi_id, type(exc).__name__)
        raise self.retry(exc=exc) from exc
    Notifikasi.objects.filter(pk=notifikasi_id).update(email_terkirim=True)
