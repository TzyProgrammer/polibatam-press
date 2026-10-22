import json

from django.contrib import admin
from django.contrib.admin import helpers

from .models import Buku, Kategori, Produk

# Tombol halaman tambah/ubah diatur global di backend/templates/admin/submit_line.html:
# satu tombol saja, "Tambah" saat menambah data dan "Simpan Perubahan" saat mengubah.


class InlineFormSetTeksTambah(helpers.InlineAdminFormSet):
    """Mengganti teks tautan "Tambahkan … lagi" pada inline dengan atribut teks_tambah milik inline."""

    def inline_formset_data(self):
        data = json.loads(super().inline_formset_data())
        teks = getattr(self.opts, "teks_tambah", None)
        if teks:
            data["options"]["addText"] = teks
        return json.dumps(data)


@admin.register(Kategori)
class KategoriAdmin(admin.ModelAdmin):
    list_display = ("nama", "slug")
    search_fields = ("nama",)
    prepopulated_fields = {"slug": ("nama",)}


class ProdukInline(admin.TabularInline):
    model = Produk
    extra = 0
    teks_tambah = "Tambah"
    fields = ("format", "harga", "stok", "berkas", "aktif", "status_drm")
    readonly_fields = ("status_drm",)

    @admin.display(description="Status DRM")
    def status_drm(self, obj):
        if not obj.pk or obj.format != Produk.Format.AUDIOBOOK:
            return "—"
        paket = getattr(obj, "paket_audio", None)
        return paket.get_status_display() if paket else "Belum diproses"


@admin.register(Buku)
class BukuAdmin(admin.ModelAdmin):
    list_display = ("judul", "penulis", "kategori", "daftar_format", "aktif", "dibuat")
    list_filter = ("aktif", "kategori", "produk__format")
    search_fields = ("judul", "penulis", "isbn")
    prepopulated_fields = {"slug": ("judul",)}
    inlines = [ProdukInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("kategori").prefetch_related("produk")

    def get_inline_formsets(self, request, formsets, inline_instances, obj=None):
        inline_formsets = super().get_inline_formsets(request, formsets, inline_instances, obj)
        for inline_formset in inline_formsets:
            inline_formset.__class__ = InlineFormSetTeksTambah
        return inline_formsets

    @admin.display(description="Format")
    def daftar_format(self, obj):
        return ", ".join(p.get_format_display() for p in obj.produk.all()) or "—"
