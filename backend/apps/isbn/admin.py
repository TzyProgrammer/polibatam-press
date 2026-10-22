from django import forms
from django.contrib import admin
from django.utils import timezone

from apps.notifications import layanan as notifikasi

from .models import PengajuanISBN


class PengajuanISBNAdminForm(forms.ModelForm):
    """Pilihan status mengikuti alur: menunggu verifikasi → diproses → selesai, atau ditolak."""

    class Meta:
        model = PengajuanISBN
        fields = ["status", "nomor_isbn", "tanggal_penetapan", "alasan_penolakan", "catatan_admin"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        kolom = self.fields.get("status")
        if kolom is not None:
            kolom.choices = [(s.value, s.label) for s in self.instance.pilihan_status()]


@admin.register(PengajuanISBN)
class PengajuanISBNAdmin(admin.ModelAdmin):
    form = PengajuanISBNAdminForm
    list_display = ("judul", "pemohon", "status", "nomor_isbn", "diajukan")
    list_filter = ("status",)
    search_fields = ("judul", "penulis", "pemohon__email", "nomor_isbn")
    date_hierarchy = "diajukan"
    readonly_fields = (
        "pemohon", "judul", "penulis", "sinopsis", "jumlah_halaman", "berkas_naskah", "diajukan", "diperbarui",
    )
    fieldsets = (
        ("Pengajuan", {"fields": (
            "pemohon", "judul", "penulis", "sinopsis", "jumlah_halaman", "berkas_naskah", "diajukan", "diperbarui",
        )}),
        ("Verifikasi", {
            "fields": ("status", "nomor_isbn", "tanggal_penetapan", "alasan_penolakan", "catatan_admin"),
            "description": "Nomor ISBN wajib diisi bila Selesai; alasan wajib diisi bila Ditolak. Setiap perubahan "
            "status dikirim sebagai notifikasi ke pemohon. Catatan admin tidak ditampilkan ke pemohon.",
        }),
    )

    def save_model(self, request, obj, form, change):
        if obj.status == PengajuanISBN.Status.SELESAI and not obj.tanggal_penetapan:
            obj.tanggal_penetapan = timezone.localdate()
        super().save_model(request, obj, form, change)
        if "status" in form.changed_data:
            notifikasi.isbn_status_berubah(obj)

    def has_add_permission(self, request):
        # Pengajuan dibuat pemohon lewat aplikasi; admin hanya memverifikasi.
        return False
