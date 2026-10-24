from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.serializers import POLA_TELEPON
from apps.catalog.serializers import url_sampul

from . import midtrans
from .checkout import KECAMATAN_KOTA_BATAM
from .models import ItemPesanan, Pesanan

PESAN_TELEPON = "Nomor telepon hanya boleh berisi angka, spasi, atau tanda hubung (boleh diawali +), 8–20 karakter."


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


class CheckoutSerializer(serializers.Serializer):
    """Isian checkout. Pengiriman hanya dipakai bila keranjang berisi buku cetak (diperiksa saat checkout).

    Nama dan nomor telepon penerima memakai data profil bila dikosongkan. Delivery wajib alamat dan
    kecamatan di Kota Batam; alamat yang disimpan: "<alamat>, Kec. <kecamatan>, Kota Batam".
    """

    metode_pengiriman = serializers.ChoiceField(
        choices=[Pesanan.MetodePengiriman.DELIVERY, Pesanan.MetodePengiriman.TAKEAWAY],
        required=False,
        allow_blank=True,
        error_messages={"invalid_choice": "Metode pengiriman harus delivery atau takeaway."},
    )
    nama_penerima = serializers.CharField(max_length=150, required=False, allow_blank=True)
    no_telepon_penerima = serializers.CharField(max_length=20, required=False, allow_blank=True)
    alamat = serializers.CharField(max_length=400, required=False, allow_blank=True)
    kecamatan = serializers.ChoiceField(
        choices=KECAMATAN_KOTA_BATAM,
        required=False,
        allow_blank=True,
        error_messages={"invalid_choice": "Delivery hanya untuk kecamatan di Kota Batam."},
    )

    def validate(self, attrs):
        metode = attrs.get("metode_pengiriman") or ""
        if not metode:
            return {"metode_pengiriman": ""}
        pembeli = self.context["pembeli"]
        nama = attrs.get("nama_penerima", "").strip() or pembeli.nama_lengkap
        telepon = attrs.get("no_telepon_penerima", "").strip() or pembeli.no_telepon
        error = {}
        if not nama:
            error["nama_penerima"] = "Nama penerima wajib diisi."
        if not telepon:
            error["no_telepon_penerima"] = "Nomor telepon wajib diisi agar penerima bisa dihubungi."
        elif not POLA_TELEPON.match(telepon):
            error["no_telepon_penerima"] = PESAN_TELEPON
        alamat_lengkap = ""
        if metode == Pesanan.MetodePengiriman.DELIVERY:
            alamat = " ".join(attrs.get("alamat", "").split())
            kecamatan = attrs.get("kecamatan", "")
            if not alamat:
                error["alamat"] = "Alamat pengiriman wajib diisi untuk delivery."
            if not kecamatan:
                error["kecamatan"] = "Pilih kecamatan di Kota Batam (delivery hanya untuk area Kota Batam)."
            alamat_lengkap = f"{alamat}, Kec. {kecamatan}, Kota Batam"
        if error:
            raise serializers.ValidationError(error)
        return {
            "metode_pengiriman": metode,
            "nama_penerima": nama,
            "no_telepon_penerima": telepon,
            "alamat_pengiriman": alamat_lengkap,
        }


class ItemPesananSerializer(serializers.ModelSerializer):
    """`judul` adalah salinan saat checkout; `buku` (slug dan sampul) data buku saat ini untuk tautan dan gambar."""

    produk_id = serializers.IntegerField()
    format_label = serializers.CharField(source="get_format_display")
    subtotal = serializers.IntegerField()
    buku = serializers.SerializerMethodField()

    class Meta:
        model = ItemPesanan
        fields = ["produk_id", "judul", "format", "format_label", "harga_satuan", "jumlah", "subtotal", "buku"]

    def get_buku(self, item):
        buku = item.produk.buku
        return {"slug": buku.slug, "sampul": url_sampul(buku)}


class PesananRingkasSerializer(serializers.ModelSerializer):
    """Satu baris riwayat pesanan (FR-12)."""

    status_pembayaran_label = serializers.CharField(source="get_status_pembayaran_display")
    metode_pengiriman_label = serializers.CharField(source="get_metode_pengiriman_display")
    status_pengiriman_label = serializers.CharField(source="get_status_pengiriman_display")
    jumlah_item = serializers.SerializerMethodField()
    ringkasan = serializers.SerializerMethodField()

    class Meta:
        model = Pesanan
        fields = [
            "nomor",
            "status_pembayaran",
            "status_pembayaran_label",
            "metode_pengiriman",
            "metode_pengiriman_label",
            "status_pengiriman",
            "status_pengiriman_label",
            "total",
            "jumlah_item",
            "ringkasan",
            "dibuat",
            "batas_bayar",
            "dibayar_pada",
        ]

    def get_jumlah_item(self, pesanan):
        return sum(item.jumlah for item in pesanan.item.all())

    def get_ringkasan(self, pesanan):
        item = list(pesanan.item.all())
        if not item:
            return ""
        lain = len(item) - 1
        return f"{item[0].judul} dan {lain} produk lain" if lain else item[0].judul


class PesananDetailSerializer(PesananRingkasSerializer):
    """Detail pesanan. `pembayaran` hanya berisi data Snap selama pesanan masih bisa dibayar."""

    item = ItemPesananSerializer(many=True)
    pengiriman = serializers.SerializerMethodField()
    pembayaran = serializers.SerializerMethodField()
    metode_pembayaran = serializers.CharField(source="midtrans_payment_type")

    class Meta(PesananRingkasSerializer.Meta):
        fields = PesananRingkasSerializer.Meta.fields + [
            "subtotal",
            "ongkir",
            "item",
            "pengiriman",
            "metode_pembayaran",
            "pembayaran",
        ]

    def get_pengiriman(self, pesanan):
        if not pesanan.perlu_pengiriman:
            return None
        data = {"nama_penerima": pesanan.nama_penerima, "no_telepon_penerima": pesanan.no_telepon_penerima}
        if pesanan.metode_pengiriman == Pesanan.MetodePengiriman.DELIVERY:
            data["alamat"] = pesanan.alamat_pengiriman
        else:
            data["lokasi_pengambilan"] = settings.LOKASI_TAKEAWAY
        return data

    def get_pembayaran(self, pesanan):
        bisa_dibayar = (
            pesanan.status_pembayaran == Pesanan.StatusPembayaran.MENUNGGU
            and pesanan.snap_token
            and pesanan.batas_bayar
            and timezone.now() < pesanan.batas_bayar
        )
        if not bisa_dibayar:
            return None
        return {
            "snap_token": pesanan.snap_token,
            "redirect_url": pesanan.snap_redirect_url,
            "client_key": settings.MIDTRANS_CLIENT_KEY,
            "snap_js": midtrans.url_snap_js(),
        }
