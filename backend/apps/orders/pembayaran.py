"""Status pembayaran dari Midtrans (FR-11, FR-12).

Satu-satunya tempat status_pembayaran berubah. Sumbernya selalu Get Status API Midtrans; notifikasi
(webhook), tombol cek status, dan pemeriksaan berkala hanya memicu pembacaan status itu. Dengan begitu
notifikasi yang terlambat, terkirim dua kali, atau tidak berurutan tidak membuat status mundur.

Transisi:
- menunggu → lunas: hak akses produk digital dibuat (salinan ebook ber-watermark ikut disiapkan),
  pengiriman buku cetak berstatus diproses, dan pembeli menerima notifikasi.
- menunggu → kedaluwarsa/dibatalkan/gagal: stok buku cetak yang dipesan saat checkout dikembalikan dan
  pembeli menerima notifikasi.
- kedaluwarsa/dibatalkan/gagal → lunas (bila Midtrans menyatakan dibayar): stok dipesan ulang, hak
  akses dibuat. Uang pembeli sudah diterima, jadi pesanan tetap lunas.
- lunas tidak pernah berubah lagi. Pengembalian dana ditangani manual (dashboard Midtrans + admin).
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.catalog.models import Produk
from apps.drm.layanan import berikan_hak_akses
from apps.notifications import layanan as notifikasi

from . import midtrans
from .models import Pesanan

logger = logging.getLogger(__name__)

Status = Pesanan.StatusPembayaran

# Midtrans mengirim status expire paling lambat sekitar 90 detik setelah kedaluwarsa.
MARGIN_KEDALUWARSA = timedelta(minutes=5)
# Waktu pada respons Midtrans memakai zona WIB (GMT+7).
ZONA_MIDTRANS = ZoneInfo("Asia/Jakarta")

STATUS_MIDTRANS = {
    "settlement": Status.LUNAS,
    "pending": Status.MENUNGGU,
    "expire": Status.KEDALUWARSA,
    "cancel": Status.DIBATALKAN,
    "deny": Status.GAGAL,
    "failure": Status.GAGAL,
}
STATUS_GAGAL = (Status.KEDALUWARSA, Status.DIBATALKAN, Status.GAGAL)


def status_dari_midtrans(data):
    """Status pembayaran lokal dari respons Status API, atau None bila tidak memengaruhi pesanan."""
    transaksi = data.get("transaction_status")
    if transaksi == "capture":  # kartu kredit
        fraud = data.get("fraud_status")
        if fraud == "accept":
            return Status.LUNAS
        if fraud == "deny":
            return Status.GAGAL
        return Status.MENUNGGU  # challenge: menunggu tinjauan di dashboard Midtrans
    # refund, chargeback, authorize, dan status lain tidak mengubah pesanan.
    return STATUS_MIDTRANS.get(transaksi)


def sinkronkan(nomor):
    """Membaca status terbaru dari Midtrans lalu menerapkannya. Melempar midtrans.GagalMidtrans."""
    data = midtrans.status_transaksi(nomor)
    return terapkan_status(nomor, data)


@transaction.atomic
def terapkan_status(nomor, data):
    """Menerapkan hasil Status API (None = transaksi belum ada di Midtrans) ke pesanan."""
    pesanan = Pesanan.objects.select_for_update().filter(nomor=nomor).first()
    if pesanan is None:
        return None
    if data is None:
        # Pembeli belum memilih metode bayar. Setelah batas bayar halaman Snap tidak bisa dipakai lagi,
        # jadi pesanan dianggap kedaluwarsa (dengan margin agar tidak mendahului Midtrans).
        if (
            pesanan.status_pembayaran == Status.MENUNGGU
            and pesanan.batas_bayar
            and timezone.now() > pesanan.batas_bayar + MARGIN_KEDALUWARSA
        ):
            _tutup_tanpa_bayar(pesanan, Status.KEDALUWARSA)
        return pesanan
    if not _sesuai_pesanan(pesanan, data):
        return pesanan

    lama = pesanan.status_pembayaran
    baru = status_dari_midtrans(data)
    _catat_transaksi(pesanan, data)
    if baru is None:
        # Misalnya refund atau chargeback: ditangani manual, pesanan tidak diubah.
        logger.info(
            "Status Midtrans %r untuk pesanan %s tidak mengubah pesanan.", data.get("transaction_status"), nomor
        )
    elif baru == lama:
        pass
    elif lama == Status.LUNAS:
        logger.warning("Pesanan %s sudah lunas; status Midtrans %r diabaikan.", nomor, data.get("transaction_status"))
    elif lama == Status.MENUNGGU and baru == Status.LUNAS:
        _lunas(pesanan, data)
    elif lama == Status.MENUNGGU:
        _tutup_tanpa_bayar(pesanan, baru)
    elif baru == Status.LUNAS:
        _lunas_setelah_ditutup(pesanan, data)
    # Selain itu: pesanan yang sudah ditutup tidak kembali menunggu atau berganti status gagal lain.
    pesanan.save(update_fields=["midtrans_transaction_id", "midtrans_payment_type", "diperbarui"])
    return pesanan


def _sesuai_pesanan(pesanan, data):
    """Data Midtrans harus untuk pesanan ini dengan nominal dan mata uang yang sama."""
    masalah = []
    if data.get("order_id") != pesanan.nomor:
        masalah.append(f"order_id {data.get('order_id')!r}")
    try:
        nominal = Decimal(str(data.get("gross_amount")))
    except InvalidOperation:
        nominal = None
    if nominal != pesanan.total:
        masalah.append(f"gross_amount {data.get('gross_amount')!r} tidak sama dengan total {pesanan.total}")
    if data.get("currency", "IDR") != "IDR":
        masalah.append(f"mata uang {data.get('currency')!r}")
    if masalah:
        logger.error("Status Midtrans untuk pesanan %s diabaikan: %s.", pesanan.nomor, "; ".join(masalah))
        return False
    return True


def _catat_transaksi(pesanan, data):
    pesanan.midtrans_transaction_id = str(data.get("transaction_id") or pesanan.midtrans_transaction_id)[:64]
    pesanan.midtrans_payment_type = str(data.get("payment_type") or pesanan.midtrans_payment_type)[:32]


def waktu_bayar(data):
    for kolom in ("settlement_time", "transaction_time"):
        try:
            waktu = datetime.strptime(str(data.get(kolom)), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        return waktu.replace(tzinfo=ZONA_MIDTRANS)
    return timezone.now()


def _lunas(pesanan, data):
    pesanan.status_pembayaran = Status.LUNAS
    pesanan.dibayar_pada = waktu_bayar(data)
    if pesanan.perlu_pengiriman:
        pesanan.status_pengiriman = Pesanan.StatusPengiriman.DIPROSES
    pesanan.save(update_fields=["status_pembayaran", "dibayar_pada", "status_pengiriman", "diperbarui"])
    for item in pesanan.item.select_related("produk", "pesanan__pembeli"):
        berikan_hak_akses(item)  # hanya produk digital; ebook sekaligus menyiapkan salinan ber-watermark
    notifikasi.pembayaran_lunas(pesanan)
    logger.info("Pesanan %s lunas (%s).", pesanan.nomor, pesanan.midtrans_payment_type or "-")


def _item_cetak(pesanan):
    return [item for item in pesanan.item.all() if item.format == Produk.Format.CETAK]


def _tutup_tanpa_bayar(pesanan, status):
    for item in _item_cetak(pesanan):
        Produk.objects.filter(pk=item.produk_id).update(stok=F("stok") + item.jumlah)
    pesanan.status_pembayaran = status
    if pesanan.perlu_pengiriman:
        pesanan.status_pengiriman = Pesanan.StatusPengiriman.TIDAK_ADA
    pesanan.save(update_fields=["status_pembayaran", "status_pengiriman", "diperbarui"])
    notifikasi.pesanan_ditutup(pesanan)
    logger.info("Pesanan %s %s; stok buku cetak dikembalikan.", pesanan.nomor, pesanan.get_status_pembayaran_display())


def _lunas_setelah_ditutup(pesanan, data):
    for item in _item_cetak(pesanan):
        dipesan = Produk.objects.filter(pk=item.produk_id, stok__gte=item.jumlah).update(stok=F("stok") - item.jumlah)
        if not dipesan:
            logger.error(
                "Pesanan %s dibayar setelah berstatus %s, tetapi stok %r tidak cukup lagi; perlu ditangani admin.",
                pesanan.nomor,
                pesanan.get_status_pembayaran_display(),
                item.judul,
            )
    logger.warning("Pesanan %s dibayar setelah berstatus %s.", pesanan.nomor, pesanan.get_status_pembayaran_display())
    _lunas(pesanan, data)
