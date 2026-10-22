from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.catalog.models import Produk

from .layanan import antrikan_pengemasan, hapus_berkas, hapus_prefix
from .models import PaketAudio, SalinanEbook


@receiver(post_save, sender=Produk, dispatch_uid="drm_kemas_saat_mp3_berubah")
def kemas_saat_mp3_berubah(sender, instance, raw=False, **kwargs):
    if raw:  # loaddata
        return
    antrikan_pengemasan(instance)


@receiver(post_delete, sender=PaketAudio, dispatch_uid="drm_hapus_hls_paket")
def hapus_hls_saat_paket_dihapus(sender, instance, **kwargs):
    prefix = instance.prefix_hls
    if prefix:
        transaction.on_commit(lambda: hapus_prefix(prefix))


@receiver(post_delete, sender=SalinanEbook, dispatch_uid="drm_hapus_pdf_salinan")
def hapus_pdf_saat_salinan_dihapus(sender, instance, **kwargs):
    nama = instance.berkas.name
    if nama:
        transaction.on_commit(lambda: hapus_berkas([nama]))
