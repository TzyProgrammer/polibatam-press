import logging
import tempfile
import uuid
from pathlib import Path

from celery import shared_task
from django.core.exceptions import ImproperlyConfigured
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from . import hls, watermark
from .kunci import enkripsi_kunci, periksa_konfigurasi
from .layanan import hapus_berkas, hapus_prefix, identitas_pembelian
from .models import PaketAudio, SalinanEbook, salinan_ebook_upload_to

logger = logging.getLogger(__name__)


def _tandai_gagal(paket_id, pesan):
    PaketAudio.objects.filter(pk=paket_id).update(status=PaketAudio.Status.GAGAL, pesan_galat=pesan[:1000])


@shared_task(soft_time_limit=2400, time_limit=2700)
def kemas_audiobook(paket_id):
    """Unduh MP3 asli, kemas menjadi HLS AES-128, unggah ke bucket, simpan kunci terenkripsi."""
    try:
        paket = PaketAudio.objects.select_related("produk").get(pk=paket_id)
    except PaketAudio.DoesNotExist:
        return "hilang"  # produk dihapus sebelum task berjalan
    sumber = paket.produk.berkas.name
    if not sumber:
        _tandai_gagal(paket_id, "Produk audiobook belum memiliki berkas MP3.")
        return "gagal"
    PaketAudio.objects.filter(pk=paket_id).update(status=PaketAudio.Status.DIPROSES, pesan_galat="")

    prefix = f"hls/{uuid.uuid4().hex}"
    terunggah = []
    try:
        periksa_konfigurasi()
        with tempfile.TemporaryDirectory(prefix="hls-") as tmp:
            folder = Path(tmp)
            path_mp3 = folder / "sumber.mp3"
            with default_storage.open(sumber, "rb") as asal, open(path_mp3, "wb") as tujuan:
                for potongan in asal.chunks():
                    tujuan.write(potongan)
            hasil = hls.kemas(path_mp3, folder)
            for path in [*hasil.segmen, folder / "index.m3u8"]:
                terunggah.append(default_storage.save(f"{prefix}/{path.name}", ContentFile(path.read_bytes())))
    except Exception as exc:
        hapus_berkas(terunggah)
        aman = isinstance(exc, (hls.GagalKemas, ImproperlyConfigured))
        logger.exception("Pengemasan paket audio %s gagal", paket_id)
        _tandai_gagal(paket_id, str(exc) if aman else "Kesalahan tak terduga; lihat log worker Celery.")
        return "gagal"

    with transaction.atomic():
        paket = PaketAudio.objects.select_for_update().get(pk=paket_id)
        if paket.berkas_sumber != sumber:
            # MP3 diganti saat proses berjalan; hasil ini usang dan task baru sudah diantrikan.
            hapus_berkas(terunggah)
            return "usang"
        prefix_lama = paket.prefix_hls
        paket.kunci_terenkripsi = enkripsi_kunci(hasil.kunci)
        paket.prefix_hls = prefix
        paket.jumlah_segmen = len(hasil.segmen)
        paket.durasi_detik = hasil.durasi_detik
        paket.status = PaketAudio.Status.SIAP
        paket.pesan_galat = ""
        paket.diproses_pada = timezone.now()
        paket.save()
    if prefix_lama and prefix_lama != prefix:
        hapus_prefix(prefix_lama)
    return "siap"


def _salinan_gagal(salinan_id, pesan):
    SalinanEbook.objects.filter(pk=salinan_id).update(status=SalinanEbook.Status.GAGAL, pesan_galat=pesan[:1000])


@shared_task(soft_time_limit=600, time_limit=660)
def buat_salinan_ebook(salinan_id):
    """Buat PDF ber-watermark milik satu pembeli dari PDF asli, lalu simpan di salinan/ebook/."""
    try:
        salinan = SalinanEbook.objects.select_related(
            "hak_akses__pembeli", "hak_akses__produk", "hak_akses__item_pesanan__pesanan"
        ).get(pk=salinan_id)
    except SalinanEbook.DoesNotExist:
        return "hilang"  # hak akses dihapus sebelum task berjalan
    sumber = salinan.hak_akses.produk.berkas.name
    if not sumber:
        _salinan_gagal(salinan_id, "Produk ebook belum memiliki berkas PDF.")
        return "gagal"
    SalinanEbook.objects.filter(pk=salinan_id).update(status=SalinanEbook.Status.DIPROSES, pesan_galat="")

    nama_baru = None
    try:
        identitas = identitas_pembelian(salinan)
        with default_storage.open(sumber, "rb") as berkas:
            asli = berkas.read()
        hasil = watermark.beri_watermark(asli, identitas)
        watermark.verifikasi_watermark(hasil, identitas)
        nama_baru = default_storage.save(salinan_ebook_upload_to(salinan, "salinan.pdf"), ContentFile(hasil))
    except Exception as exc:
        if nama_baru:
            hapus_berkas([nama_baru])
        aman = isinstance(exc, (watermark.GagalWatermark, ImproperlyConfigured))
        logger.exception("Pembuatan salinan ebook %s gagal", salinan_id)
        _salinan_gagal(salinan_id, str(exc) if aman else "Kesalahan tak terduga; lihat log worker Celery.")
        return "gagal"

    with transaction.atomic():
        salinan = SalinanEbook.objects.select_for_update().filter(pk=salinan_id).first()
        if salinan is None:
            hapus_berkas([nama_baru])
            return "hilang"
        nama_lama = salinan.berkas.name
        salinan.berkas.name = nama_baru
        salinan.status = SalinanEbook.Status.SIAP
        salinan.pesan_galat = ""
        salinan.siap_pada = timezone.now()
        salinan.save(update_fields=["berkas", "status", "pesan_galat", "siap_pada"])
    if nama_lama and nama_lama != nama_baru:
        hapus_berkas([nama_lama])
    return "siap"
