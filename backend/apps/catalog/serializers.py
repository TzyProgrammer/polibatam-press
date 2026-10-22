from django.core.files.storage import default_storage
from rest_framework import serializers

from .ketersediaan import ketersediaan
from .models import Buku, Kategori, Produk

# Sampul bukan konten berbayar, jadi presigned URL-nya boleh lebih lama dari bawaan 5 menit
# agar gambar tidak cepat kedaluwarsa saat pembeli menelusuri katalog.
UMUR_URL_SAMPUL = 60 * 60


def url_sampul(buku):
    if not buku.sampul:
        return None
    return default_storage.url(buku.sampul.name, expire=UMUR_URL_SAMPUL)


class KategoriSerializer(serializers.ModelSerializer):
    jumlah_buku = serializers.IntegerField(read_only=True)

    class Meta:
        model = Kategori
        fields = ["id", "nama", "slug", "jumlah_buku"]


class KategoriRingkasSerializer(serializers.ModelSerializer):
    class Meta:
        model = Kategori
        fields = ["nama", "slug"]


class ProdukKatalogSerializer(serializers.ModelSerializer):
    format_label = serializers.CharField(source="get_format_display", read_only=True)

    class Meta:
        model = Produk
        fields = ["id", "format", "format_label", "harga"]

    def to_representation(self, produk):
        data = super().to_representation(produk)
        tersedia, keterangan = ketersediaan(produk)
        data["stok"] = produk.stok if produk.format == Produk.Format.CETAK else None
        data["tersedia"] = tersedia
        data["keterangan"] = keterangan
        return data


class BukuRingkasSerializer(serializers.ModelSerializer):
    """Satu kartu buku di daftar katalog."""

    kategori = KategoriRingkasSerializer(read_only=True)
    sampul = serializers.SerializerMethodField()
    harga_mulai = serializers.IntegerField(read_only=True)
    produk = ProdukKatalogSerializer(source="produk_aktif", many=True, read_only=True)

    class Meta:
        model = Buku
        fields = ["id", "judul", "slug", "penulis", "kategori", "sampul", "harga_mulai", "produk"]

    def get_sampul(self, buku):
        return url_sampul(buku)


class BukuDetailSerializer(BukuRingkasSerializer):
    class Meta(BukuRingkasSerializer.Meta):
        fields = [
            *BukuRingkasSerializer.Meta.fields,
            "sinopsis", "isbn", "tahun_terbit", "jumlah_halaman", "ukuran",
        ]
