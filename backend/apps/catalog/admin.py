import json

from django import forms
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import ProtectedError
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils.html import format_html

from .models import Buku, Kategori, Produk

# Tombol halaman tambah/ubah diatur global di backend/templates/admin/submit_line.html:
# satu tombol saja, "Tambah" saat menambah data dan "Simpan Perubahan" saat mengubah.

PREFIX_PRODUK = "produk"  # prefix formset inline produk (related_name Produk.buku)


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


class InputBerkasDenganHapus(forms.ClearableFileInput):
    """Input berkas produk: berkas tersimpan ditampilkan dengan tombol "Hapus" (modal konfirmasi di
    admin-buku.js), menggantikan kotak centang "Hapus" + Simpan bawaan Django."""

    template_name = "catalog/widgets/berkas_dengan_hapus.html"

    def __init__(self, attrs=None):
        super().__init__(attrs)
        self.url_hapus = ""
        self.pesan_hapus = ""

    def get_context(self, name, value, attrs):
        konteks = super().get_context(name, value, attrs)
        konteks["widget"]["url_hapus"] = self.url_hapus
        konteks["widget"]["pesan_hapus"] = self.pesan_hapus
        return konteks


def pesan_hapus_berkas(produk):
    if produk.format == Produk.Format.AUDIOBOOK:
        return (
            "Berkas MP3 asli dan paket HLS terenkripsinya dihapus permanen dari penyimpanan. Audiobook tidak "
            "bisa dibeli atau diputar sampai berkas baru diunggah dan dikemas ulang."
        )
    return (
        "Berkas PDF asli dihapus permanen dari penyimpanan. Ebook tidak bisa dibeli sampai berkas baru "
        "diunggah. Salinan ber-watermark milik pembeli yang sudah ada tidak terpengaruh."
    )


class ProdukInlineForm(forms.ModelForm):
    class Meta:
        model = Produk
        fields = ("format", "harga", "stok", "berkas", "aktif")
        widgets = {"berkas": InputBerkasDenganHapus}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        produk = self.instance
        if produk.pk and produk.berkas:
            widget = self.fields["berkas"].widget
            widget.url_hapus = reverse("admin:catalog_produk_hapus_berkas", args=[produk.pk])
            widget.pesan_hapus = pesan_hapus_berkas(produk)

    def clean(self):
        data = super().clean()
        # Stok tidak berlaku untuk produk digital (kolomnya dikunci di halaman admin).
        if data.get("format") and data["format"] != Produk.Format.CETAK:
            data["stok"] = 0
            self.instance.stok = 0
        return data


class ProdukInlineFormSet(forms.BaseInlineFormSet):
    def get_unique_error_message(self, unique_check):
        # Format ganda ditangkap validate_unique() bawaan formset (UniqueConstraint buku + format).
        if set(unique_check) == {"buku", "format"}:
            return "Setiap format hanya boleh satu kali per buku."
        return super().get_unique_error_message(unique_check)

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        ada_produk = any(
            form.cleaned_data.get("format")
            for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get("DELETE")
        )
        if not ada_produk:
            raise forms.ValidationError(
                "Tambahkan minimal 1 produk (buku cetak, ebook, atau audiobook) sebelum menyimpan buku."
            )


class ProdukInline(admin.TabularInline):
    model = Produk
    form = ProdukInlineForm
    formset = ProdukInlineFormSet
    extra = 0
    min_num = 1  # buku baru langsung menampilkan satu baris produk dan wajib memiliki minimal satu
    max_num = len(Produk.Format.choices)  # satu baris per format; tombol Tambah hilang bila ketiganya ada
    can_delete = False  # penghapusan lewat tombol Hapus + modal konfirmasi (kolom "Hapus")
    teks_tambah = "Tambah"
    fields = ("format", "harga", "stok", "berkas", "aktif", "status_drm", "tombol_hapus")
    readonly_fields = ("status_drm", "tombol_hapus")

    @admin.display(description="Status DRM")
    def status_drm(self, obj):
        if not obj.pk or obj.format != Produk.Format.AUDIOBOOK:
            return "—"
        paket = getattr(obj, "paket_audio", None)
        return paket.get_status_display() if paket else "Belum diproses"

    @admin.display(description="Hapus")
    def tombol_hapus(self, obj):
        if not obj or not obj.pk:
            return ""
        return format_html(
            '<button type="button" class="tombol-hapus" data-hapus-produk="{}" data-format="{}">Hapus</button>',
            reverse("admin:catalog_produk_hapus", args=[obj.pk]),
            obj.get_format_display(),
        )


class BukuAdminForm(forms.ModelForm):
    """Semua data buku wajib diisi (keputusan pemilik, 26 Oktober), kecuali jumlah halaman dan ukuran yang
    hanya wajib untuk buku yang punya produk cetak atau ebook (tidak berlaku untuk audiobook saja)."""

    WAJIB = ("judul", "penulis", "sinopsis", "kategori", "isbn", "tahun_terbit", "sampul")
    WAJIB_UNTUK_BACAAN = (("jumlah_halaman", "Jumlah halaman"), ("ukuran", "Ukuran"))

    class Meta:
        model = Buku
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nama in self.WAJIB:
            if nama in self.fields:
                self.fields[nama].required = True

    def format_produk_dikirim(self):
        """Format produk yang dikirim bersama formulir ini (baris inline yang tidak dihapus)."""
        try:
            jumlah = int(self.data.get(f"{PREFIX_PRODUK}-TOTAL_FORMS") or 0)
        except ValueError:
            return set()
        hasil = set()
        for i in range(min(jumlah, 10)):
            nilai = self.data.get(f"{PREFIX_PRODUK}-{i}-format")
            if nilai and not self.data.get(f"{PREFIX_PRODUK}-{i}-DELETE"):
                hasil.add(nilai)
        return hasil

    def clean(self):
        data = super().clean()
        if self.format_produk_dikirim() & {Produk.Format.CETAK, Produk.Format.EBOOK}:
            for nama, label in self.WAJIB_UNTUK_BACAAN:
                if nama in self.fields and not data.get(nama):
                    self.add_error(nama, f"{label} wajib diisi untuk buku yang memiliki produk cetak atau ebook.")
        return data


@admin.register(Buku)
class BukuAdmin(admin.ModelAdmin):
    form = BukuAdminForm
    list_display = ("judul", "penulis", "kategori", "daftar_format", "aktif", "dibuat")
    list_filter = ("aktif", "kategori", "produk__format")
    search_fields = ("judul", "penulis", "isbn")
    prepopulated_fields = {"slug": ("judul",)}
    inlines = [ProdukInline]

    class Media:
        js = ("polibatam/admin-modal.js", "polibatam/admin-buku.js")

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

    # Tombol Hapus pada baris produk (berkas dan produknya) bekerja langsung setelah dikonfirmasi di modal.
    def get_urls(self):
        return [
            path(
                "produk/<int:pk>/hapus-berkas/",
                self.admin_site.admin_view(self.hapus_berkas_produk),
                name="catalog_produk_hapus_berkas",
            ),
            path(
                "produk/<int:pk>/hapus/",
                self.admin_site.admin_view(self.hapus_produk),
                name="catalog_produk_hapus",
            ),
        ] + super().get_urls()

    def hapus_berkas_produk(self, request, pk):
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        if not request.user.has_perm("catalog.change_produk"):
            raise PermissionDenied
        produk = get_object_or_404(Produk.objects.select_related("buku"), pk=pk)
        nama = produk.berkas.name
        if not nama:
            return JsonResponse({"pesan": "Produk ini tidak memiliki berkas."}, status=400)
        # Impor di sini: app drm bergantung pada catalog, bukan sebaliknya.
        from apps.drm.layanan import hapus_berkas
        from apps.drm.models import PaketAudio

        with transaction.atomic():
            # update() melewati sinyal post_save (pengemasan HLS) dan validasi "wajib berkas": produk sengaja
            # dibiarkan tanpa berkas (tidak bisa dibeli) sampai admin mengunggah berkas baru.
            Produk.objects.filter(pk=produk.pk).update(berkas="")
            if produk.format == Produk.Format.AUDIOBOOK:
                PaketAudio.objects.filter(produk=produk).delete()  # segmen HLS ikut dihapus (sinyal drm)
            transaction.on_commit(lambda: hapus_berkas([nama]))
        pesan = f"Berkas {produk.get_format_display()} untuk “{produk.buku.judul}” dihapus."
        self.log_change(request, produk.buku, pesan)
        messages.success(request, pesan)
        return JsonResponse({"pesan": pesan})

    def hapus_produk(self, request, pk):
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        if not request.user.has_perm("catalog.delete_produk"):
            raise PermissionDenied
        produk = get_object_or_404(Produk.objects.select_related("buku"), pk=pk)
        buku = produk.buku
        if Produk.objects.filter(buku=buku).count() <= 1:
            return JsonResponse(
                {"pesan": "Buku harus memiliki minimal 1 produk. Tambahkan produk lain dahulu, atau hapus bukunya."},
                status=400,
            )
        label = produk.get_format_display()
        try:
            with transaction.atomic():
                produk.delete()  # berkas asli ikut dihapus dari penyimpanan (sinyal drm)
        except ProtectedError:
            return JsonResponse(
                {
                    "pesan": "Produk ini sudah pernah dipesan, jadi tidak bisa dihapus agar riwayat pesanan tetap "
                    "utuh. Hapus centang Aktif untuk berhenti menjualnya."
                },
                status=409,
            )
        pesan = f"Produk {label} untuk “{buku.judul}” dihapus."
        self.log_change(request, buku, pesan)
        messages.success(request, pesan)
        return JsonResponse({"pesan": pesan})
