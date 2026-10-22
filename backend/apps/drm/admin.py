from django.contrib import admin

from .layanan import antrikan_pengemasan
from .models import HakAkses, LogAksesKunci, PaketAudio, SalinanEbook, SesiStreaming


class HanyaBacaMixin:
    """Data jejak keamanan: boleh dilihat, tidak boleh dibuat, diubah, atau dihapus dari admin."""

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


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
class PaketAudioAdmin(admin.ModelAdmin):
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

    def has_add_permission(self, request):
        return False


@admin.register(SalinanEbook)
class SalinanEbookAdmin(admin.ModelAdmin):
    list_display = ("kode_watermark", "pembeli", "produk", "status", "siap_pada")
    list_filter = ("status",)
    search_fields = ("kode_watermark", "hak_akses__pembeli__email", "hak_akses__produk__buku__judul")
    fields = ("kode_watermark", "hak_akses", "status", "berkas", "pesan_galat", "dibuat", "siap_pada")
    readonly_fields = fields

    @admin.display(description="Pembeli")
    def pembeli(self, obj):
        return obj.hak_akses.pembeli

    @admin.display(description="Produk")
    def produk(self, obj):
        return obj.hak_akses.produk

    def has_add_permission(self, request):
        return False


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
