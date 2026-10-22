import secrets

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.catalog.models import Produk


class Keranjang(models.Model):
    pembeli = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="keranjang")
    diperbarui = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "keranjang"
        verbose_name_plural = "keranjang"

    def __str__(self):
        return f"Keranjang {self.pembeli}"


class ItemKeranjang(models.Model):
    keranjang = models.ForeignKey(Keranjang, on_delete=models.CASCADE, related_name="item")
    produk = models.ForeignKey(Produk, on_delete=models.CASCADE, related_name="+")
    jumlah = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    ditambahkan = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "item keranjang"
        verbose_name_plural = "item keranjang"
        constraints = [
            models.UniqueConstraint(fields=["keranjang", "produk"], name="item_keranjang_unik"),
        ]

    @property
    def subtotal(self):
        return self.produk.harga * self.jumlah

    def __str__(self):
        return f"{self.produk} × {self.jumlah}"


class Pesanan(models.Model):
    class StatusPembayaran(models.TextChoices):
        MENUNGGU = "menunggu", "Menunggu pembayaran"
        LUNAS = "lunas", "Lunas"
        KEDALUWARSA = "kedaluwarsa", "Kedaluwarsa"
        DIBATALKAN = "dibatalkan", "Dibatalkan"
        GAGAL = "gagal", "Gagal"

    class MetodePengiriman(models.TextChoices):
        TANPA = "tanpa", "Tanpa pengiriman (produk digital)"
        DELIVERY = "delivery", "Delivery (area Kota Batam)"
        TAKEAWAY = "takeaway", "Takeaway (ambil sendiri)"

    class StatusPengiriman(models.TextChoices):
        TIDAK_ADA = "tidak_ada", "Tidak ada (produk digital)"
        MENUNGGU = "menunggu", "Menunggu pembayaran"
        DIPROSES = "diproses", "Diproses"
        DIKIRIM = "dikirim", "Dikirim"
        SIAP_DIAMBIL = "siap_diambil", "Siap diambil"
        SELESAI = "selesai", "Selesai"

    nomor = models.CharField(max_length=32, unique=True, editable=False)
    pembeli = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="pesanan")
    # Status pembayaran hanya diubah oleh notifikasi Midtrans yang tanda tangannya valid.
    status_pembayaran = models.CharField(
        max_length=12, choices=StatusPembayaran.choices, default=StatusPembayaran.MENUNGGU, db_index=True
    )
    metode_pengiriman = models.CharField(
        max_length=10, choices=MetodePengiriman.choices, default=MetodePengiriman.TANPA
    )
    status_pengiriman = models.CharField(
        max_length=12, choices=StatusPengiriman.choices, default=StatusPengiriman.TIDAK_ADA
    )
    nama_penerima = models.CharField(max_length=150, blank=True)
    no_telepon_penerima = models.CharField(max_length=20, blank=True)
    alamat_pengiriman = models.TextField(blank=True)
    subtotal = models.PositiveIntegerField(default=0)
    ongkir = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)
    snap_token = models.CharField(max_length=100, blank=True)
    snap_redirect_url = models.URLField(max_length=500, blank=True)
    midtrans_transaction_id = models.CharField(max_length=64, blank=True)
    midtrans_payment_type = models.CharField(max_length=32, blank=True)
    dibayar_pada = models.DateTimeField(null=True, blank=True)
    dibuat = models.DateTimeField(auto_now_add=True)
    diperbarui = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "pesanan"
        verbose_name_plural = "pesanan"
        ordering = ["-dibuat"]

    def save(self, *args, **kwargs):
        if not self.nomor:
            self.nomor = self.buat_nomor()
        super().save(*args, **kwargs)

    @classmethod
    def buat_nomor(cls):
        """Nomor pesanan sekaligus order_id Midtrans, contoh PP-20261022-A1B2C3."""
        tanggal = timezone.localdate().strftime("%Y%m%d")
        while True:
            nomor = f"PP-{tanggal}-{secrets.token_hex(3).upper()}"
            if not cls.objects.filter(nomor=nomor).exists():
                return nomor

    def __str__(self):
        return self.nomor


class ItemPesanan(models.Model):
    pesanan = models.ForeignKey(Pesanan, on_delete=models.CASCADE, related_name="item")
    produk = models.ForeignKey(Produk, on_delete=models.PROTECT, related_name="+")
    # Salinan data saat pesanan dibuat, agar riwayat tidak berubah bila produk diedit.
    judul = models.CharField(max_length=255)
    format = models.CharField(max_length=10, choices=Produk.Format.choices)
    harga_satuan = models.PositiveIntegerField()
    jumlah = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta:
        verbose_name = "item pesanan"
        verbose_name_plural = "item pesanan"

    @property
    def subtotal(self):
        return self.harga_satuan * self.jumlah

    def __str__(self):
        return f"{self.judul} ({self.get_format_display()}) × {self.jumlah}"


class LogNotifikasiMidtrans(models.Model):
    """Arsip setiap notifikasi pembayaran yang diterima, termasuk yang ditolak."""

    pesanan = models.ForeignKey(
        Pesanan, on_delete=models.SET_NULL, null=True, blank=True, related_name="log_midtrans"
    )
    order_id = models.CharField(max_length=64, db_index=True)
    transaction_status = models.CharField(max_length=32, blank=True)
    signature_valid = models.BooleanField(default=False)
    payload = models.JSONField()
    diterima = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "log notifikasi Midtrans"
        verbose_name_plural = "log notifikasi Midtrans"
        ordering = ["-diterima"]

    def __str__(self):
        return f"{self.order_id} {self.transaction_status}"
