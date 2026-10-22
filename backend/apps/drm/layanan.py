import logging

from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Produk

from .models import HakAkses, PaketAudio, SalinanEbook
from .watermark import IdentitasPembelian, samarkan_email

logger = logging.getLogger(__name__)


def berikan_hak_akses(item_pesanan):
    """Hak akses pembeli atas produk digital pada satu item pesanan lunas.

    Dipakai alur pembayaran (Tahap F) dan perintah uji buat_akses_uji. Untuk ebook, salinan
    ber-watermark ikut disiapkan. Aman dipanggil berulang: hak akses yang sudah ada dipakai lagi.
    """
    produk = item_pesanan.produk
    if not produk.is_digital:
        return None
    hak, _ = HakAkses.objects.get_or_create(
        pembeli=item_pesanan.pesanan.pembeli, produk=produk, defaults={"item_pesanan": item_pesanan}
    )
    siapkan_salinan_ebook(hak)
    return hak


def siapkan_salinan_ebook(hak_akses, paksa=False):
    """Buat SalinanEbook (kode watermark otomatis) dan antrikan pembuatan PDF ber-watermark.

    Tanpa paksa, salinan yang sudah ada tidak dibuat ulang. Mengembalikan salinan, atau None
    bila produk bukan ebook.
    """
    from .tasks import buat_salinan_ebook  # impor di sini agar tidak melingkar saat app dimuat

    if hak_akses.produk.format != Produk.Format.EBOOK:
        return None
    salinan, dibuat = SalinanEbook.objects.get_or_create(hak_akses=hak_akses)
    if not dibuat and not paksa:
        return salinan
    salinan.status = SalinanEbook.Status.MENUNGGU
    salinan.pesan_galat = ""
    salinan.save(update_fields=["status", "pesan_galat"])
    salinan_id = salinan.pk
    transaction.on_commit(lambda: buat_salinan_ebook.delay(salinan_id))
    return salinan


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


def identitas_pembelian(salinan):
    """Data yang dicetak pada watermark salinan ebook."""
    hak = salinan.hak_akses
    pembeli = hak.pembeli
    pesanan = hak.item_pesanan.pesanan
    waktu_beli = timezone.localtime(pesanan.dibayar_pada or pesanan.dibuat)
    return IdentitasPembelian(
        kode=salinan.kode_watermark,
        nama=pembeli.nama_lengkap or pembeli.email.partition("@")[0],
        email_samaran=samarkan_email(pembeli.email),
        nomor_pesanan=pesanan.nomor,
        tanggal=waktu_beli.strftime("%d-%m-%Y"),
    )


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
