import logging
from collections import Counter

from celery import shared_task

from . import midtrans
from .models import Pesanan
from .pembayaran import sinkronkan

logger = logging.getLogger(__name__)


@shared_task
def periksa_pesanan_menunggu(batas=100):
    """Dijalankan celery-beat tiap 5 menit: pesanan yang menunggu pembayaran dicocokkan dengan Status API.

    Menangkap pembayaran yang notifikasinya tidak sampai (misalnya tanpa tunnel webhook saat uji lokal)
    dan menutup pesanan yang melewati batas bayar sehingga stok buku cetak kembali.
    """
    nomor_menunggu = list(
        Pesanan.objects.filter(status_pembayaran=Pesanan.StatusPembayaran.MENUNGGU)
        .order_by("dibuat")
        .values_list("nomor", flat=True)[:batas]
    )
    hasil = Counter()
    for nomor in nomor_menunggu:
        try:
            pesanan = sinkronkan(nomor)
        except midtrans.BelumDikonfigurasi as exc:
            logger.warning("Pemeriksaan pesanan dilewati: %s", exc)
            break
        except midtrans.GagalMidtrans as exc:
            logger.warning("Status pesanan %s belum bisa diperiksa: %s", nomor, exc)
            hasil["gagal_diperiksa"] += 1
            continue
        if pesanan is not None:
            hasil[str(pesanan.status_pembayaran)] += 1
    if nomor_menunggu:
        logger.info("Pemeriksaan %d pesanan menunggu: %s", len(nomor_menunggu), dict(hasil))
    return dict(hasil)
