from django import forms
from django.contrib import admin
from django.utils import timezone

from apps.notifications import layanan as notifikasi

from .models import PengajuanISBN


Status = PengajuanISBN.Status

# Kolom yang hanya berlaku untuk status tertentu. Di halaman admin kolom lain dikunci (admin-isbn.js) dan
# server mengosongkannya, sehingga nomor ISBN tidak tersimpan pada pengajuan yang ditolak dan alasan penolakan
# tidak tersimpan pada pengajuan yang selesai.
KOLOM_PER_STATUS = {
    "nomor_isbn": (Status.SELESAI,),
    "tanggal_penetapan": (Status.SELESAI,),
    "alasan_penolakan": (Status.DITOLAK,),
}


class PengajuanISBNAdminForm(forms.ModelForm):
    """Pilihan status mengikuti alur: menunggu verifikasi → diproses → selesai atau ditolak."""

    class Meta:
        model = PengajuanISBN
        fields = ["status", "nomor_isbn", "tanggal_penetapan", "alasan_penolakan", "catatan_admin"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        kolom = self.fields.get("status")
        if kolom is not None:
            kolom.choices = [(s.value, s.label) for s in self.instance.pilihan_status()]
        for nama, daftar_status in KOLOM_PER_STATUS.items():
            if nama in self.fields:
                self.fields[nama].widget.attrs["data-status-berlaku"] = " ".join(daftar_status)

    def clean(self):
        data = super().clean()
        status = data.get("status")
        if status:
            for nama, daftar_status in KOLOM_PER_STATUS.items():
                if nama in self.fields and status not in daftar_status:
                    data[nama] = None if nama == "tanggal_penetapan" else ""
                    self.errors.pop(nama, None)  # isian kolom terkunci diabaikan, termasuk yang tidak valid
        return data


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
            "description": "Pengajuan baru dilanjutkan ke Diproses; keputusan Selesai atau Ditolak diambil saat "
            "Diproses. Nomor ISBN dan tanggal penetapan hanya diisi bila Selesai (nomor wajib), alasan penolakan "
            "hanya bila Ditolak (wajib). Setiap perubahan status dikirim sebagai notifikasi ke pemohon. Catatan "
            "admin tidak ditampilkan ke pemohon.",
        }),
    )

    class Media:
        js = ("polibatam/admin-isbn.js",)

    def save_model(self, request, obj, form, change):
        if obj.status == PengajuanISBN.Status.SELESAI and not obj.tanggal_penetapan:
            obj.tanggal_penetapan = timezone.localdate()
        super().save_model(request, obj, form, change)
        if "status" in form.changed_data:
            notifikasi.isbn_status_berubah(obj)

    def has_add_permission(self, request):
        # Pengajuan dibuat pemohon lewat aplikasi; admin hanya memverifikasi.
        return False
