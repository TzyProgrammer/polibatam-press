from django.contrib import admin

from .models import PengajuanISBN


@admin.register(PengajuanISBN)
class PengajuanISBNAdmin(admin.ModelAdmin):
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
        ("Verifikasi", {"fields": ("status", "nomor_isbn", "tanggal_penetapan", "alasan_penolakan", "catatan_admin")}),
    )

    def has_add_permission(self, request):
        return False
