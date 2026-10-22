from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.catalog.models import Produk, nama_berkas_unik

from .kode import buat_kode_watermark


def salinan_ebook_upload_to(instance, filename):
    return nama_berkas_unik("salinan/ebook", filename)


class HakAkses(models.Model):
    """Hak pembeli atas satu produk digital. Dibuat saat pembayaran pesanan lunas."""

    pembeli = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="hak_akses")
    produk = models.ForeignKey(Produk, on_delete=models.PROTECT, related_name="hak_akses")
    item_pesanan = models.OneToOneField("orders.ItemPesanan", on_delete=models.PROTECT, related_name="hak_akses")
    aktif = models.BooleanField(default=True, help_text="Matikan untuk mencabut akses tanpa menghapus riwayat.")
    diberikan = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "hak akses"
        verbose_name_plural = "hak akses"
        ordering = ["-diberikan"]
        constraints = [
            models.UniqueConstraint(fields=["pembeli", "produk"], name="hak_akses_unik_per_produk"),
        ]

    def __str__(self):
        return f"{self.pembeli} → {self.produk}"


class PaketAudio(models.Model):
    """Hasil enkripsi AES-128 HLS sebuah audiobook (sekali per buku, saat diunggah)."""

    class Status(models.TextChoices):
        MENUNGGU = "menunggu", "Menunggu diproses"
        DIPROSES = "diproses", "Sedang diproses"
        SIAP = "siap", "Siap diputar"
        GAGAL = "gagal", "Gagal"

    produk = models.OneToOneField(
        Produk,
        on_delete=models.CASCADE,
        related_name="paket_audio",
        limit_choices_to={"format": Produk.Format.AUDIOBOOK},
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.MENUNGGU)
    # Kunci AES-128 (16 byte) terenkripsi Fernet dengan FERNET_MASTER_KEY. Tidak pernah ditampilkan.
    kunci_terenkripsi = models.BinaryField(null=True, editable=False)
    prefix_hls = models.CharField(max_length=255, blank=True, help_text="Lokasi playlist dan segmen di bucket.")
    berkas_sumber = models.CharField(max_length=255, blank=True, help_text="Nama objek MP3 yang diproses.")
    jumlah_segmen = models.PositiveIntegerField(default=0)
    durasi_detik = models.PositiveIntegerField(default=0)
    pesan_galat = models.TextField(blank=True)
    diproses_pada = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "paket audio (HLS)"
        verbose_name_plural = "paket audio (HLS)"

    def __str__(self):
        return f"{self.produk} [{self.get_status_display()}]"


class SesiStreaming(models.Model):
    """Sesi pemutaran bertoken berumur pendek untuk satu pembeli dan satu audiobook."""

    pembeli = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sesi_streaming")
    paket = models.ForeignKey(PaketAudio, on_delete=models.CASCADE, related_name="sesi")
    # Hanya hash SHA-256 yang disimpan; token asli hanya diketahui pembeli.
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    kedaluwarsa = models.DateTimeField(db_index=True)
    dicabut = models.BooleanField(default=False)
    alamat_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    dibuat = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "sesi streaming"
        verbose_name_plural = "sesi streaming"
        ordering = ["-dibuat"]

    @property
    def masih_berlaku(self):
        return not self.dicabut and timezone.now() < self.kedaluwarsa

    def __str__(self):
        return f"{self.pembeli} – {self.paket.produk} ({timezone.localtime(self.dibuat):%d-%m-%Y %H:%M})"


class LogAksesKunci(models.Model):
    """Jejak setiap permintaan kunci AES, diizinkan maupun ditolak (bahan uji keamanan)."""

    class Hasil(models.TextChoices):
        DIIZINKAN = "diizinkan", "Diizinkan"
        DITOLAK = "ditolak", "Ditolak"

    sesi = models.ForeignKey(SesiStreaming, on_delete=models.SET_NULL, null=True, blank=True, related_name="log_kunci")
    pengguna = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    paket = models.ForeignKey(PaketAudio, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    hasil = models.CharField(max_length=10, choices=Hasil.choices)
    alasan = models.CharField(max_length=100, blank=True)
    alamat_ip = models.GenericIPAddressField(null=True, blank=True)
    waktu = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "log akses kunci"
        verbose_name_plural = "log akses kunci"
        ordering = ["-waktu"]

    def __str__(self):
        return f"{self.get_hasil_display()} {self.alasan} ({timezone.localtime(self.waktu):%d-%m-%Y %H:%M:%S})"


class SalinanEbook(models.Model):
    """Salinan PDF ber-watermark milik satu pembeli (sekali per pembelian, saat lunas)."""

    class Status(models.TextChoices):
        MENUNGGU = "menunggu", "Menunggu diproses"
        DIPROSES = "diproses", "Sedang diproses"
        SIAP = "siap", "Siap dibaca"
        GAGAL = "gagal", "Gagal"

    hak_akses = models.OneToOneField(HakAkses, on_delete=models.CASCADE, related_name="salinan_ebook")
    kode_watermark = models.CharField(max_length=19, unique=True, editable=False)
    berkas = models.FileField(upload_to=salinan_ebook_upload_to, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.MENUNGGU)
    pesan_galat = models.TextField(blank=True)
    dibuat = models.DateTimeField(auto_now_add=True)
    siap_pada = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "salinan ebook"
        verbose_name_plural = "salinan ebook"
        ordering = ["-dibuat"]

    def save(self, *args, **kwargs):
        if not self.kode_watermark:
            hak = self.hak_akses
            self.kode_watermark = buat_kode_watermark(hak.pembeli_id, hak.item_pesanan_id, hak.produk_id)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.kode_watermark
