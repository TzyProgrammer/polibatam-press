from django.contrib import admin
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.template.response import TemplateResponse
from django.urls import path

from .forms import FormLacakKebocoran
from .lacak import lacak_kebocoran
from .layanan import antrikan_pengemasan, siapkan_salinan_ebook
from .models import HakAkses, LogAksesKunci, PaketAudio, SalinanEbook, SesiStreaming
from .watermark import GagalWatermark


class HanyaBacaMixin:
    """Data hasil sistem: hanya bisa dilihat di admin (tanpa tombol simpan dan tanpa hapus).

    Izin hapus sengaja tidak dimatikan: Django Admin memeriksa izin hapus setiap objek terkait
    sebelum menghapus induknya, sehingga tanpa izin itu buku/produk audiobook tidak bisa dihapus.
    Data ini ikut terhapus bersama induknya, tetapi tidak bisa dihapus satu per satu.
    Aksi admin lain (misalnya "Proses ulang") tetap tersedia.
    """

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        aksi = super().get_actions(request)
        aksi.pop("delete_selected", None)
        return aksi

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = {**(extra_context or {}), "show_delete": False}
        return super().change_view(request, object_id, form_url, extra_context)

    def delete_view(self, request, object_id, extra_context=None):
        raise PermissionDenied


@admin.register(HakAkses)
class HakAksesAdmin(admin.ModelAdmin):
    list_display = ("pembeli", "produk", "aktif", "diberikan")
    list_filter = ("aktif", "produk__format")
    search_fields = ("pembeli__email", "produk__buku__judul")
    readonly_fields = ("pembeli", "produk", "item_pesanan", "diberikan")
    fields = ("pembeli", "produk", "item_pesanan", "aktif", "diberikan")

    def has_add_permission(self, request):
        return False


@admin.register(PaketAudio)
class PaketAudioAdmin(HanyaBacaMixin, admin.ModelAdmin):
    """Hanya dilihat (tanpa tombol simpan); pemrosesan ulang lewat aksi "Proses ulang"."""

    list_display = ("produk", "status", "ada_kunci", "jumlah_segmen", "durasi_detik", "diproses_pada")
    list_filter = ("status",)
    search_fields = ("produk__buku__judul",)
    fields = (
        "produk", "status", "ada_kunci", "prefix_hls", "berkas_sumber", "jumlah_segmen", "durasi_detik",
        "pesan_galat", "diproses_pada",
    )
    readonly_fields = fields
    actions = ["proses_ulang"]

    @admin.display(description="Kunci tersimpan", boolean=True)
    def ada_kunci(self, obj):
        # Hanya keberadaan kunci yang ditampilkan, tidak pernah isinya.
        return bool(obj.kunci_terenkripsi)

    @admin.action(description="Proses ulang paket audio terpilih")
    def proses_ulang(self, request, queryset):
        jumlah = sum(1 for paket in queryset.select_related("produk") if antrikan_pengemasan(paket.produk, paksa=True))
        self.message_user(request, f"{jumlah} paket audio diantrekan untuk diproses ulang.")


@admin.register(SalinanEbook)
class SalinanEbookAdmin(HanyaBacaMixin, admin.ModelAdmin):
    """Hanya dilihat; aksi "Proses ulang" dan halaman "Lacak kebocoran" (FR-16)."""

    list_display = ("kode_watermark", "pembeli", "produk", "status", "siap_pada")
    list_filter = ("status",)
    search_fields = ("kode_watermark", "hak_akses__pembeli__email", "hak_akses__produk__buku__judul")
    list_select_related = ("hak_akses__pembeli", "hak_akses__produk__buku")
    fields = ("kode_watermark", "hak_akses", "status", "berkas", "pesan_galat", "dibuat", "siap_pada")
    readonly_fields = fields
    actions = ["proses_ulang"]
    change_list_template = "admin/drm/salinanebook/change_list.html"

    @admin.display(description="Pembeli")
    def pembeli(self, obj):
        return obj.hak_akses.pembeli

    @admin.display(description="Produk")
    def produk(self, obj):
        return obj.hak_akses.produk

    @admin.action(description="Proses ulang salinan ebook terpilih")
    def proses_ulang(self, request, queryset):
        jumlah = sum(
            1 for salinan in queryset.select_related("hak_akses__produk")
            if siapkan_salinan_ebook(salinan.hak_akses, paksa=True)
        )
        self.message_user(request, f"{jumlah} salinan ebook diantrekan untuk diproses ulang.")

    def get_urls(self):
        lacak = path(
            "lacak-kebocoran/", self.admin_site.admin_view(self.lacak_view), name="drm_salinanebook_lacak"
        )
        return [lacak, *super().get_urls()]

    def lacak_view(self, request):
        """Unggah PDF yang diduga bocor → kode watermark → pembeli dan pesanan."""
        if not self.has_view_permission(request):
            raise PermissionDenied
        hasil = nama_berkas = None
        if request.method == "POST":
            form = FormLacakKebocoran(request.POST, request.FILES)
            if form.is_valid():
                berkas = form.cleaned_data["berkas"]
                nama_berkas = berkas.name
                try:
                    hasil = lacak_kebocoran(berkas.read())
                except GagalWatermark as exc:
                    form.add_error("berkas", str(exc))
                except ImproperlyConfigured as exc:
                    form.add_error(None, str(exc))
        else:
            form = FormLacakKebocoran()
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Lacak kebocoran ebook",
            "form": form,
            "hasil": hasil,
            "nama_berkas": nama_berkas,
        }
        return TemplateResponse(request, "admin/drm/salinanebook/lacak.html", context)


@admin.register(SesiStreaming)
class SesiStreamingAdmin(HanyaBacaMixin, admin.ModelAdmin):
    list_display = ("pembeli", "paket", "dibuat", "kedaluwarsa", "dicabut", "alamat_ip")
    list_filter = ("dicabut",)
    search_fields = ("pembeli__email",)
    exclude = ("token_hash",)


@admin.register(LogAksesKunci)
class LogAksesKunciAdmin(HanyaBacaMixin, admin.ModelAdmin):
    list_display = ("waktu", "hasil", "alasan", "pengguna", "paket", "alamat_ip")
    list_filter = ("hasil", "alasan")
    search_fields = ("pengguna__email",)
    date_hierarchy = "waktu"
