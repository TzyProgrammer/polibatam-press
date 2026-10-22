from django.core.files.storage import default_storage
from django.utils.text import slugify
from rest_framework import serializers

from .models import PengajuanISBN
from .validators import validasi_isi_naskah

# Pengajuan yang masih berjalan (menunggu verifikasi atau diproses) per pemohon.
BATAS_PENGAJUAN_AKTIF = 5
STATUS_AKTIF = (PengajuanISBN.Status.MENUNGGU_VERIFIKASI, PengajuanISBN.Status.DIPROSES)


class PengajuanBaruSerializer(serializers.ModelSerializer):
    """POST multipart: judul, penulis, sinopsis, jumlah_halaman (opsional), berkas_naskah (.pdf/.docx)."""

    class Meta:
        model = PengajuanISBN
        fields = ["judul", "penulis", "sinopsis", "jumlah_halaman", "berkas_naskah"]
        extra_kwargs = {"jumlah_halaman": {"min_value": 1}}

    def validate_berkas_naskah(self, berkas):
        validasi_isi_naskah(berkas)  # ValidationError Django diubah DRF menjadi error pada kolom ini
        return berkas

    def validate(self, attrs):
        pemohon = self.context["request"].user
        if PengajuanISBN.objects.filter(pemohon=pemohon, status__in=STATUS_AKTIF).count() >= BATAS_PENGAJUAN_AKTIF:
            raise serializers.ValidationError(
                f"Anda sudah memiliki {BATAS_PENGAJUAN_AKTIF} pengajuan yang belum selesai. "
                "Tunggu hingga salah satunya selesai atau ditolak."
            )
        return attrs


class PengajuanSerializer(serializers.ModelSerializer):
    """Pengajuan milik pemohon. Nomor ISBN hanya tampil bila selesai, alasan hanya bila ditolak;
    catatan internal admin tidak pernah ditampilkan."""

    status_label = serializers.CharField(source="get_status_display", read_only=True)
    nomor_isbn = serializers.SerializerMethodField()
    alasan_penolakan = serializers.SerializerMethodField()

    class Meta:
        model = PengajuanISBN
        fields = [
            "id",
            "judul",
            "penulis",
            "status",
            "status_label",
            "nomor_isbn",
            "tanggal_penetapan",
            "alasan_penolakan",
            "diajukan",
            "diperbarui",
        ]

    def get_nomor_isbn(self, pengajuan):
        return pengajuan.nomor_isbn if pengajuan.status == PengajuanISBN.Status.SELESAI else ""

    def get_alasan_penolakan(self, pengajuan):
        return pengajuan.alasan_penolakan if pengajuan.status == PengajuanISBN.Status.DITOLAK else ""


class PengajuanDetailSerializer(PengajuanSerializer):
    """Detail pengajuan beserta tautan unduh naskah milik pemohon (presigned URL 5 menit)."""

    naskah = serializers.SerializerMethodField()

    class Meta(PengajuanSerializer.Meta):
        fields = PengajuanSerializer.Meta.fields + ["sinopsis", "jumlah_halaman", "naskah"]

    def get_naskah(self, pengajuan):
        if not pengajuan.berkas_naskah:
            return None
        ekstensi = pengajuan.berkas_naskah.name.rsplit(".", 1)[-1].lower()
        nama = f"naskah-{slugify(pengajuan.judul) or pengajuan.pk}.{ekstensi}"
        url = default_storage.url(
            pengajuan.berkas_naskah.name,
            parameters={"ResponseContentDisposition": f'attachment; filename="{nama}"'},
            expire=300,
        )
        return {"format": ekstensi, "nama": nama, "url": url}
