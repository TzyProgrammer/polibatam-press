"""Hak akses uji untuk pengujian lokal sebelum alur checkout dan Midtrans (Tahap F) tersedia."""

import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.models import Produk
from apps.drm.models import HakAkses, PaketAudio
from apps.orders.models import ItemPesanan, Pesanan

PENANDA_UJI = "uji-lokal"


class Command(BaseCommand):
    help = (
        "Khusus pengujian lokal (DJANGO_DEBUG=True): memberi pembeli hak akses ke audiobook tanpa checkout. "
        "Membuat pesanan uji bertanda midtrans_payment_type='uji-lokal'. Tanpa --produk: menampilkan daftar audiobook."
    )

    def add_arguments(self, parser):
        parser.add_argument("--email", help="Email akun pembeli.")
        parser.add_argument("--produk", type=int, help="ID produk audiobook.")
        parser.add_argument("--cabut", action="store_true", help="Menonaktifkan hak akses (uji penolakan 403).")

    def handle(self, *args, **opsi):
        if not settings.DEBUG:
            raise CommandError("Perintah ini hanya untuk pengujian lokal dengan DJANGO_DEBUG=True.")
        if not opsi["produk"]:
            self.tampilkan_audiobook()
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
        if produk.format != Produk.Format.AUDIOBOOK:
            raise CommandError("Saat ini hanya produk audiobook yang didukung (ebook menyusul di Tahap D).")

        with transaction.atomic():
            hak = HakAkses.objects.select_for_update().filter(pembeli=pembeli, produk=produk).first()
            if opsi["cabut"]:
                if hak is None:
                    raise CommandError("Pembeli ini belum memiliki hak akses ke produk tersebut.")
                hak.aktif = False
                hak.save(update_fields=["aktif"])
                self.stdout.write(self.style.WARNING(f"Hak akses {pembeli} ke {produk} dinonaktifkan."))
                return
            if hak is None:
                hak = self.buat_hak_akses(pembeli, produk)
                self.stdout.write(self.style.SUCCESS(f"Hak akses dibuat (pesanan uji {hak.item_pesanan.pesanan})."))
            elif not hak.aktif:
                hak.aktif = True
                hak.save(update_fields=["aktif"])
                self.stdout.write(self.style.SUCCESS("Hak akses yang sudah ada diaktifkan kembali."))
            else:
                self.stdout.write("Hak akses sudah ada dan aktif.")

        paket = PaketAudio.objects.filter(produk=produk).first()
        status = paket.get_status_display() if paket else "belum ada paket"
        port = os.environ.get("NGINX_HOST_PORT", "8080")
        self.stdout.write(f"Pembeli : {pembeli}")
        self.stdout.write(f"Produk  : [{produk.pk}] {produk}")
        self.stdout.write(f"Paket   : {status}")
        if paket is None or paket.status != PaketAudio.Status.SIAP:
            self.stdout.write(self.style.WARNING("Paket audio belum siap; tunggu worker Celery selesai."))
        self.stdout.write(f"Buka http://localhost:{port}/uji-pemutar/?produk={produk.pk} lalu login sebagai {pembeli}.")

    def buat_hak_akses(self, pembeli, produk):
        # Pesanan uji dibuat langsung lunas karena alur Midtrans belum tersedia; penandanya
        # midtrans_payment_type="uji-lokal" sehingga mudah dibedakan dari pesanan sungguhan.
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
        item = ItemPesanan.objects.create(
            pesanan=pesanan,
            produk=produk,
            judul=produk.buku.judul,
            format=produk.format,
            harga_satuan=produk.harga,
            jumlah=1,
        )
        return HakAkses.objects.create(pembeli=pembeli, produk=produk, item_pesanan=item)

    def tampilkan_audiobook(self):
        daftar = Produk.objects.select_related("buku", "paket_audio").filter(format=Produk.Format.AUDIOBOOK)
        if not daftar:
            self.stdout.write("Belum ada produk audiobook. Tambahkan lewat Admin → Buku (format Audiobook + MP3).")
            return
        self.stdout.write("Produk audiobook:")
        for produk in daftar.order_by("pk"):
            paket = getattr(produk, "paket_audio", None)
            status = paket.get_status_display() if paket else "belum ada paket"
            self.stdout.write(f"  [{produk.pk}] {produk.buku.judul} — {status}")
        self.stdout.write("Pemakaian: python manage.py buat_akses_uji --email <email pembeli> --produk <ID>")
