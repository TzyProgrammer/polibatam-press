from django import forms
from django.conf import settings
from django.contrib import admin, messages

from apps.notifications import layanan as notifikasi

from . import midtrans
from .models import ItemPesanan, LogNotifikasiMidtrans, Pesanan
from .pembayaran import sinkronkan

# Batas pesanan per sekali aksi "Cek status" (setiap pesanan = satu permintaan ke Midtrans).
BATAS_CEK_STATUS = 20


class ItemPesananInline(admin.TabularInline):
    model = ItemPesanan
    extra = 0
    can_delete = False
    fields = ("judul", "format", "harga_satuan", "jumlah", "subtotal")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class PesananAdminForm(forms.ModelForm):
    """Status pengiriman hanya bisa dipilih sesuai metode: delivery diproses → dikirim → selesai,
    takeaway diproses → siap diambil → selesai."""

    class Meta:
        model = Pesanan
        fields = ["status_pengiriman"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        kolom = self.fields.get("status_pengiriman")
        if kolom is not None:
            kolom.choices = [(s.value, s.label) for s in self.instance.pilihan_status_pengiriman()]


@admin.register(Pesanan)
class PesananAdmin(admin.ModelAdmin):
    form = PesananAdminForm
    list_display = (
        "nomor", "pembeli", "status_pembayaran", "metode_pengiriman", "status_pengiriman", "total", "dibuat",
    )
    list_filter = ("status_pembayaran", "metode_pengiriman", "status_pengiriman")
    search_fields = ("nomor", "pembeli__email", "pembeli__nama_lengkap")
    date_hierarchy = "dibuat"
    inlines = [ItemPesananInline]
    actions = ["cek_status_midtrans"]
    # Admin hanya boleh mengubah status pengiriman. Status pembayaran hanya dari Midtrans.
    readonly_fields = (
        "nomor", "pembeli", "status_pembayaran", "batas_bayar", "dibayar_pada", "metode_pengiriman",
        "nama_penerima", "no_telepon_penerima", "alamat_pengiriman", "lokasi_pengambilan",
        "subtotal", "ongkir", "total",
        "midtrans_transaction_id", "midtrans_payment_type", "dibuat", "diperbarui",
    )
    fieldsets = (
        ("Pesanan", {"fields": ("nomor", "pembeli", "dibuat", "diperbarui")}),
        ("Pembayaran", {"fields": (
            "status_pembayaran", "batas_bayar", "dibayar_pada", "subtotal", "ongkir", "total",
            "midtrans_transaction_id", "midtrans_payment_type",
        )}),
        ("Pengiriman", {"fields": (
            "metode_pengiriman", "status_pengiriman", "nama_penerima", "no_telepon_penerima", "alamat_pengiriman",
            "lokasi_pengambilan",
        )}),
    )

    def get_readonly_fields(self, request, obj=None):
        kolom = list(super().get_readonly_fields(request, obj))
        if obj is None or not obj.pilihan_status_pengiriman():
            # Belum lunas atau tanpa buku cetak: belum ada yang perlu dikirim.
            kolom.append("status_pengiriman")
        return kolom

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if "status_pengiriman" in form.changed_data:
            notifikasi.pengiriman_berubah(obj)

    @admin.display(description="Lokasi pengambilan")
    def lokasi_pengambilan(self, obj):
        return settings.LOKASI_TAKEAWAY if obj.metode_pengiriman == Pesanan.MetodePengiriman.TAKEAWAY else "-"

    @admin.action(description="Cek status pembayaran ke Midtrans")
    def cek_status_midtrans(self, request, queryset):
        menunggu = list(
            queryset.filter(status_pembayaran=Pesanan.StatusPembayaran.MENUNGGU).values_list("nomor", flat=True)
        )
        if not menunggu:
            self.message_user(request, "Tidak ada pesanan terpilih yang menunggu pembayaran.", messages.INFO)
            return
        hasil, gagal = [], []
        for nomor in menunggu[:BATAS_CEK_STATUS]:
            try:
                pesanan = sinkronkan(nomor)
            except midtrans.GagalMidtrans:
                gagal.append(nomor)
                continue
            hasil.append(f"{nomor}: {pesanan.get_status_pembayaran_display()}")
        if hasil:
            self.message_user(request, "Status dari Midtrans: " + ", ".join(hasil) + ".", messages.SUCCESS)
        if gagal:
            self.message_user(
                request, "Midtrans belum bisa dihubungi untuk: " + ", ".join(gagal) + ".", messages.WARNING
            )
        if len(menunggu) > BATAS_CEK_STATUS:
            self.message_user(
                request,
                f"Hanya {BATAS_CEK_STATUS} pesanan pertama yang diperiksa; ulangi untuk sisanya.",
                messages.INFO,
            )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        # Pesanan adalah catatan transaksi; menghapusnya juga akan menghilangkan stok yang sedang dipesan.
        return False


@admin.register(LogNotifikasiMidtrans)
class LogNotifikasiMidtransAdmin(admin.ModelAdmin):
    list_display = ("order_id", "transaction_status", "signature_valid", "pesanan", "diterima")
    list_filter = ("signature_valid", "transaction_status")
    search_fields = ("order_id",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
