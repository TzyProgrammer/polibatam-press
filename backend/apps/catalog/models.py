import uuid
from pathlib import PurePosixPath

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify


def nama_berkas_unik(prefix, filename):
    """Nama objek acak agar nama asli berkas tidak bocor dan tidak bisa ditebak."""
    ext = PurePosixPath(filename).suffix.lower()
    return f"{prefix}/{uuid.uuid4().hex}{ext}"


def sampul_upload_to(instance, filename):
    return nama_berkas_unik("sampul", filename)


def berkas_asli_upload_to(instance, filename):
    # Berkas asli konten digital. Hanya dibaca worker DRM, tidak pernah dikirim ke pembeli.
    return nama_berkas_unik(f"asli/{instance.format}", filename)


class Kategori(models.Model):
    nama = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)

    class Meta:
        verbose_name = "kategori"
        verbose_name_plural = "kategori"
        ordering = ["nama"]

    def __str__(self):
        return self.nama


class Buku(models.Model):
    judul = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    penulis = models.CharField(max_length=255, help_text="Pisahkan beberapa penulis dengan titik koma.")
    sinopsis = models.TextField(blank=True)
    kategori = models.ForeignKey(
        Kategori, on_delete=models.SET_NULL, null=True, blank=True, related_name="buku"
    )
    isbn = models.CharField("ISBN", max_length=20, blank=True)
    tahun_terbit = models.PositiveSmallIntegerField(null=True, blank=True)
    jumlah_halaman = models.PositiveIntegerField(null=True, blank=True)
    ukuran = models.CharField(max_length=50, blank=True, help_text="Contoh: 14,8 x 21 cm")
    sampul = models.FileField(
        upload_to=sampul_upload_to,
        blank=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
    )
    aktif = models.BooleanField(default=True, help_text="Hanya buku aktif yang tampil di katalog.")
    dibuat = models.DateTimeField(auto_now_add=True)
    diperbarui = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "buku"
        verbose_name_plural = "buku"
        ordering = ["-dibuat"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._slug_unik()
        super().save(*args, **kwargs)

    def _slug_unik(self):
        dasar = slugify(self.judul)[:270] or "buku"
        slug, nomor = dasar, 2
        while Buku.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f"{dasar}-{nomor}"
            nomor += 1
        return slug

    def __str__(self):
        return self.judul


class Produk(models.Model):
    """Satu format jual dari sebuah buku: cetak, ebook, atau audiobook."""

    class Format(models.TextChoices):
        CETAK = "cetak", "Buku cetak"
        EBOOK = "ebook", "Ebook (PDF)"
        AUDIOBOOK = "audiobook", "Audiobook (MP3)"

    # Ekstensi berkas asli yang diterima untuk tiap format digital.
    EKSTENSI_BERKAS = {"ebook": "pdf", "audiobook": "mp3"}

    buku = models.ForeignKey(Buku, on_delete=models.CASCADE, related_name="produk")
    format = models.CharField(max_length=10, choices=Format.choices)
    harga = models.PositiveIntegerField(validators=[MinValueValidator(1)], help_text="Rupiah, tanpa titik.")
    stok = models.PositiveIntegerField(
        default=0,
        help_text="Hanya untuk buku cetak. Stok yang masih bisa dijual: berkurang saat checkout dan "
        "kembali bila pesanan tidak dibayar sampai batas waktu.",
    )
    berkas = models.FileField(
        upload_to=berkas_asli_upload_to,
        blank=True,
        help_text="PDF untuk ebook, MP3 untuk audiobook. Tidak pernah diberikan langsung ke pembeli.",
    )
    aktif = models.BooleanField(default=True)

    class Meta:
        verbose_name = "produk"
        verbose_name_plural = "produk"
        ordering = ["buku", "format"]
        constraints = [
            models.UniqueConstraint(fields=["buku", "format"], name="produk_unik_per_format"),
        ]

    @property
    def is_digital(self):
        return self.format != self.Format.CETAK

    def clean(self):
        super().clean()
        errors = {}
        if self.format == self.Format.CETAK:
            if self.berkas:
                errors["berkas"] = "Buku cetak tidak memakai berkas digital."
        elif self.format in self.EKSTENSI_BERKAS:
            ekstensi = self.EKSTENSI_BERKAS[self.format]
            if not self.berkas:
                errors["berkas"] = f"Produk {self.get_format_display()} wajib memiliki berkas .{ekstensi}."
            elif PurePosixPath(self.berkas.name).suffix.lower() != f".{ekstensi}":
                errors["berkas"] = f"Berkas {self.get_format_display()} harus berekstensi .{ekstensi}."
            if self.stok:
                errors["stok"] = "Stok hanya dipakai untuk buku cetak."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.buku.judul} ({self.get_format_display()})"
