"""Hak akses uji untuk pengujian lokal tanpa checkout dan Midtrans.

Hanya untuk debug (DJANGO_DEBUG=True). Sesuai keputusan pemilik, perintah ini dan pesanan bertanda
"uji-lokal" dihapus saat aplikasi final sehingga semua hak akses lahir dari pembayaran Midtrans.
"""

import os

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.models import Produk
from apps.drm.layanan import berikan_hak_akses
from apps.drm.models import HakAkses, PaketAudio, SalinanEbook
from apps.orders.models import ItemPesanan, Pesanan

PENANDA_UJI = "uji-lokal"
FORMAT_DIGITAL = (Produk.Format.AUDIOBOOK, Produk.Format.EBOOK)


class Command(BaseCommand):
    help = (
        "Khusus pengujian lokal (DJANGO_DEBUG=True): memberi pembeli hak akses ke audiobook atau ebook tanpa "
        "checkout. Membuat pesanan uji bertanda midtrans_payment_type='uji-lokal'. Tanpa --produk: menampilkan "
        "daftar produk digital."
    )

    def add_arguments(self, parser):
        parser.add_argument("--email", help="Email akun pembeli.")
        parser.add_argument("--produk", type=int, help="ID produk audiobook atau ebook.")
        parser.add_argument("--cabut", action="store_true", help="Menonaktifkan hak akses (uji penolakan 403).")

    def handle(self, *args, **opsi):
        if not settings.DEBUG:
            raise CommandError("Perintah ini hanya untuk pengujian lokal dengan DJANGO_DEBUG=True.")
        if not opsi["produk"]:
            self.tampilkan_produk_digital()
            return
        if not opsi["email"]:
            raise CommandError("Isi --email dengan email akun pembeli.")

        try:
            pembeli = User.objects.get(email__iexact=opsi["email"].strip())
        except User.DoesNotExist:
            raise CommandError(
                f"Akun {opsi['email']} tidak ditemukan. Daftar dulu lewat halaman uji pemutar atau admin."
            ) from None
        produk = Produk.objects.select_related("buku").filter(pk=opsi["produk"]).first()
        if produk is None:
            raise CommandError(f"Produk dengan ID {opsi['produk']} tidak ditemukan.")
        if produk.format not in FORMAT_DIGITAL:
            raise CommandError("Hanya produk digital (audiobook atau ebook) yang memakai hak akses.")

        try:
            with transaction.atomic():
                self.atur_hak_akses(pembeli, produk, opsi["cabut"])
        except ImproperlyConfigured as exc:
            raise CommandError(str(exc)) from exc
        if not opsi["cabut"]:
            self.tampilkan_status(pembeli, produk)

    def atur_hak_akses(self, pembeli, produk, cabut):
        hak = HakAkses.objects.select_for_update().filter(pembeli=pembeli, produk=produk).first()
        if cabut:
            if hak is None:
                raise CommandError("Pembeli ini belum memiliki hak akses ke produk tersebut.")
            hak.aktif = False
            hak.save(update_fields=["aktif"])
            self.stdout.write(self.style.WARNING(f"Hak akses {pembeli} ke {produk} dinonaktifkan."))
        elif hak is None:
            hak = berikan_hak_akses(self.buat_item_pesanan_uji(pembeli, produk))
            self.stdout.write(self.style.SUCCESS(f"Hak akses dibuat (pesanan uji {hak.item_pesanan.pesanan})."))
        elif not hak.aktif:
            hak.aktif = True
            hak.save(update_fields=["aktif"])
            self.stdout.write(self.style.SUCCESS("Hak akses yang sudah ada diaktifkan kembali."))
        else:
            self.stdout.write("Hak akses sudah ada dan aktif.")

    def buat_item_pesanan_uji(self, pembeli, produk):
        # Pesanan uji dibuat langsung lunas tanpa Midtrans; penandanya midtrans_payment_type="uji-lokal"
        # sehingga mudah dibedakan dari pesanan sungguhan.
        pesanan = Pesanan.objects.create(
            pembeli=pembeli,
            status_pembayaran=Pesanan.StatusPembayaran.LUNAS,
            metode_pengiriman=Pesanan.MetodePengiriman.TANPA,
            status_pengiriman=Pesanan.StatusPengiriman.TIDAK_ADA,
            subtotal=produk.harga,
            total=produk.harga,
            midtrans_payment_type=PENANDA_UJI,
            dibayar_pada=timezone.now(),
        )
        return ItemPesanan.objects.create(
            pesanan=pesanan,
            produk=produk,
            judul=produk.buku.judul,
            format=produk.format,
            harga_satuan=produk.harga,
            jumlah=1,
        )

    def tampilkan_status(self, pembeli, produk):
        port = os.environ.get("NGINX_HOST_PORT", "8080")
        self.stdout.write(f"Pembeli : {pembeli}")
        self.stdout.write(f"Produk  : [{produk.pk}] {produk}")
        if produk.format == Produk.Format.AUDIOBOOK:
            paket = PaketAudio.objects.filter(produk=produk).first()
            self.stdout.write(f"Paket   : {paket.get_status_display() if paket else 'belum ada paket'}")
            if paket is None or paket.status != PaketAudio.Status.SIAP:
                self.stdout.write(self.style.WARNING("Paket audio belum siap; tunggu worker Celery selesai."))
            parameter = f"produk={produk.pk}"
        else:
            salinan = SalinanEbook.objects.filter(hak_akses__pembeli=pembeli, hak_akses__produk=produk).first()
            if salinan is None:
                self.stdout.write("Salinan : belum ada (dibuat saat pembeli membuka ebook)")
            else:
                self.stdout.write(f"Salinan : {salinan.get_status_display()} (kode {salinan.kode_watermark})")
            if salinan is None or salinan.status != SalinanEbook.Status.SIAP:
                self.stdout.write(self.style.WARNING("Salinan ber-watermark dibuat worker Celery; tunggu sebentar."))
            parameter = f"ebook={produk.pk}"
        self.stdout.write(f"Buka http://localhost:{port}/uji-pemutar/?{parameter} lalu login sebagai {pembeli}.")

    def tampilkan_produk_digital(self):
        daftar = (
            Produk.objects.select_related("buku", "paket_audio")
            .filter(format__in=FORMAT_DIGITAL)
            .order_by("format", "pk")
        )
        if not daftar:
            self.stdout.write("Belum ada produk digital. Tambahkan lewat Admin → Buku (Audiobook/MP3 atau Ebook/PDF).")
            return
        self.stdout.write("Produk digital:")
        for produk in daftar:
            if produk.format == Produk.Format.AUDIOBOOK:
                paket = getattr(produk, "paket_audio", None)
                status = paket.get_status_display() if paket else "belum ada paket"
            else:
                status = "salinan ber-watermark dibuat per pembeli"
            self.stdout.write(f"  [{produk.pk}] {produk} — {status}")
        self.stdout.write("Pemakaian: python manage.py buat_akses_uji --email <email pembeli> --produk <ID>")
