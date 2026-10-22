from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models

from apps.catalog.models import nama_berkas_unik

from .validators import validasi_isbn13


def naskah_upload_to(instance, filename):
    return nama_berkas_unik("isbn/naskah", filename)


class PengajuanISBN(models.Model):
    """Permohonan nomor ISBN oleh pembeli. Pengurusan ke Perpusnas dilakukan admin di luar sistem."""

    class Status(models.TextChoices):
        MENUNGGU_VERIFIKASI = "menunggu_verifikasi", "Menunggu verifikasi"
        DIPROSES = "diproses", "Diproses"
        SELESAI = "selesai", "Selesai"
        DITOLAK = "ditolak", "Ditolak"

    pemohon = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="pengajuan_isbn")
    judul = models.CharField(max_length=255)
    penulis = models.CharField(max_length=255, help_text="Pisahkan beberapa penulis dengan titik koma.")
    sinopsis = models.TextField()
    jumlah_halaman = models.PositiveIntegerField(null=True, blank=True)
    berkas_naskah = models.FileField(
        upload_to=naskah_upload_to,
        validators=[FileExtensionValidator(["pdf", "docx"])],
        help_text="Naskah dalam format PDF atau DOCX.",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.MENUNGGU_VERIFIKASI, db_index=True
    )
    nomor_isbn = models.CharField("nomor ISBN", max_length=17, blank=True, validators=[validasi_isbn13])
    tanggal_penetapan = models.DateField(null=True, blank=True)
    alasan_penolakan = models.TextField(blank=True)
    catatan_admin = models.TextField(blank=True, help_text="Catatan internal, tidak ditampilkan ke pemohon.")
    diajukan = models.DateTimeField(auto_now_add=True)
    diperbarui = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "pengajuan ISBN"
        verbose_name_plural = "pengajuan ISBN"
        ordering = ["-diajukan"]

    def pilihan_status(self):
        """Status yang boleh dipilih admin: menunggu verifikasi → diproses → selesai, atau ditolak.

        Selesai dan ditolak adalah status akhir; naskah yang ditolak diajukan ulang sebagai pengajuan baru.
        """
        alur = {
            self.Status.MENUNGGU_VERIFIKASI: [self.Status.DIPROSES, self.Status.DITOLAK],
            self.Status.DIPROSES: [self.Status.SELESAI, self.Status.DITOLAK],
        }
        return [self.Status(self.status), *alur.get(self.status, [])]

    def clean(self):
        super().clean()
        errors = {}
        if self.status == self.Status.SELESAI and not self.nomor_isbn:
            errors["nomor_isbn"] = "Nomor ISBN wajib diisi bila status Selesai."
        if self.status == self.Status.DITOLAK and not self.alasan_penolakan.strip():
            errors["alasan_penolakan"] = "Alasan penolakan wajib diisi bila status Ditolak."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.judul} ({self.get_status_display()})"
