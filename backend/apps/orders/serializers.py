from rest_framework import serializers

from apps.catalog.serializers import url_sampul


class TambahItemSerializer(serializers.Serializer):
    produk_id = serializers.IntegerField(min_value=1)
    jumlah = serializers.IntegerField(min_value=1, default=1)


class UbahJumlahSerializer(serializers.Serializer):
    jumlah = serializers.IntegerField(min_value=1)


def data_keranjang(isi):
    """Representasi JSON hasil apps.orders.keranjang.ringkasan()."""
    item = []
    for baris in isi["baris"]:
        i = baris["item"]
        produk = i.produk
        item.append(
            {
                "id": i.id,
                "jumlah": i.jumlah,
                "subtotal": i.subtotal,
                "tersedia": baris["tersedia"],
                "keterangan": baris["keterangan"],
                "produk": {
                    "id": produk.id,
                    "format": produk.format,
                    "format_label": produk.get_format_display(),
                    "harga": produk.harga,
                    "stok": produk.stok if not produk.is_digital else None,
                    "buku": {
                        "judul": produk.buku.judul,
                        "slug": produk.buku.slug,
                        "sampul": url_sampul(produk.buku),
                    },
                },
            }
        )
    return {
        "item": item,
        "jumlah_item": isi["jumlah_item"],
        "total": isi["total"],
        "perlu_pengiriman": isi["perlu_pengiriman"],
        "semua_tersedia": isi["semua_tersedia"],
    }
