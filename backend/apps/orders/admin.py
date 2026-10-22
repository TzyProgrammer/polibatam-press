from django.contrib import admin

from .models import ItemPesanan, LogNotifikasiMidtrans, Pesanan


class ItemPesananInline(admin.TabularInline):
    model = ItemPesanan
    extra = 0
    can_delete = False
    fields = ("judul", "format", "harga_satuan", "jumlah", "subtotal")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Pesanan)
class PesananAdmin(admin.ModelAdmin):
    list_display = (
        "nomor", "pembeli", "status_pembayaran", "metode_pengiriman", "status_pengiriman", "total", "dibuat",
    )
    list_filter = ("status_pembayaran", "metode_pengiriman", "status_pengiriman")
    search_fields = ("nomor", "pembeli__email", "pembeli__nama_lengkap")
    date_hierarchy = "dibuat"
    inlines = [ItemPesananInline]
    # Admin hanya boleh mengubah status pengiriman. Status pembayaran hanya dari Midtrans.
    readonly_fields = (
        "nomor", "pembeli", "status_pembayaran", "dibayar_pada", "metode_pengiriman",
        "nama_penerima", "no_telepon_penerima", "alamat_pengiriman",
        "subtotal", "ongkir", "total",
        "midtrans_transaction_id", "midtrans_payment_type", "dibuat", "diperbarui",
    )
    fieldsets = (
        ("Pesanan", {"fields": ("nomor", "pembeli", "dibuat", "diperbarui")}),
        ("Pembayaran", {"fields": (
            "status_pembayaran", "dibayar_pada", "subtotal", "ongkir", "total",
            "midtrans_transaction_id", "midtrans_payment_type",
        )}),
        ("Pengiriman", {"fields": (
            "metode_pengiriman", "status_pengiriman", "nama_penerima", "no_telepon_penerima", "alamat_pengiriman",
        )}),
    )

    def has_add_permission(self, request):
        return False


@admin.register(LogNotifikasiMidtrans)
class LogNotifikasiMidtransAdmin(admin.ModelAdmin):
    list_display = ("order_id", "transaction_status", "signature_valid", "diterima")
    list_filter = ("signature_valid", "transaction_status")
    search_fields = ("order_id",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
