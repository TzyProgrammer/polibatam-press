from django.conf import settings
from django.db import models


class Notifikasi(models.Model):
    """Notifikasi di dalam aplikasi (ikon lonceng). Kolom email_terkirim disiapkan untuk pengiriman email kelak."""

    class Kategori(models.TextChoices):
        PESANAN = "pesanan", "Pesanan"
        KONTEN = "konten", "Konten digital"
        ISBN = "isbn", "ISBN"
        SISTEM = "sistem", "Sistem"

    penerima = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifikasi")
    kategori = models.CharField(max_length=10, choices=Kategori.choices, default=Kategori.SISTEM)
    judul = models.CharField(max_length=150)
    pesan = models.TextField()
    tautan = models.CharField(max_length=255, blank=True, help_text="Path halaman frontend, mis. /pesanan/PP-...")
    dibaca = models.BooleanField(default=False, db_index=True)
    email_terkirim = models.BooleanField(default=False)
    dibuat = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "notifikasi"
        verbose_name_plural = "notifikasi"
        ordering = ["-dibuat", "-id"]

    def __str__(self):
        return f"{self.penerima}: {self.judul}"
