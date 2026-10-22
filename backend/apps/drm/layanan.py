import logging

from django.core.files.storage import default_storage
from django.db import transaction

from apps.catalog.models import Produk

from .models import PaketAudio

logger = logging.getLogger(__name__)


def antrikan_pengemasan(produk, paksa=False):
    """Siapkan PaketAudio dan antrikan pengemasan HLS untuk produk audiobook.

    Tanpa paksa, hanya berjalan bila berkas MP3 baru atau berganti. Mengembalikan paket
    yang diantrikan, atau None bila tidak ada yang perlu dikemas.
    """
    from .tasks import kemas_audiobook  # impor di sini agar tidak melingkar saat app dimuat

    if produk.format != Produk.Format.AUDIOBOOK or not produk.berkas:
        return None
    paket, _ = PaketAudio.objects.get_or_create(produk=produk)
    if not paksa and paket.berkas_sumber == produk.berkas.name:
        return None
    paket.status = PaketAudio.Status.MENUNGGU
    paket.pesan_galat = ""
    paket.berkas_sumber = produk.berkas.name
    paket.save(update_fields=["status", "pesan_galat", "berkas_sumber"])
    paket_id = paket.pk
    transaction.on_commit(lambda: kemas_audiobook.delay(paket_id))
    return paket


def hapus_berkas(daftar_nama):
    """Hapus objek di bucket satu per satu; kegagalan dicatat, tidak menghentikan proses."""
    for nama in daftar_nama:
        try:
            default_storage.delete(nama)
        except Exception:
            logger.warning("Gagal menghapus %s dari bucket", nama, exc_info=True)


def hapus_prefix(prefix):
    if not prefix:
        return
    try:
        _, berkas = default_storage.listdir(prefix)
    except Exception:
        logger.warning("Gagal membaca isi %s", prefix, exc_info=True)
        return
    hapus_berkas(f"{prefix}/{nama}" for nama in berkas)
