import logging

from django.conf import settings
from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import checkout, midtrans, pembayaran
from . import keranjang as layanan
from .models import LogNotifikasiMidtrans, Pesanan
from .serializers import (
    CheckoutSerializer,
    PesananDetailSerializer,
    PesananRingkasSerializer,
    TambahItemSerializer,
    UbahJumlahSerializer,
    data_keranjang,
)

logger = logging.getLogger(__name__)


def respons_keranjang(keranjang, kode=status.HTTP_200_OK):
    return Response(data_keranjang(layanan.ringkasan(keranjang)), status=kode)


def respons_gagal(exc):
    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


def _item_tidak_ditemukan():
    return Response({"detail": "Item keranjang tidak ditemukan."}, status=status.HTTP_404_NOT_FOUND)


class KeranjangView(APIView):
    """GET /api/keranjang/ — isi keranjang pembeli (dibuat otomatis bila belum ada)."""

    def get(self, request):
        return respons_keranjang(layanan.keranjang_milik(request.user))


class TambahItemView(APIView):
    """POST /api/keranjang/item/ {produk_id, jumlah} — mengembalikan isi keranjang terbaru."""

    def post(self, request):
        data = TambahItemSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            keranjang = layanan.tambah_item(request.user, **data.validated_data)
        except layanan.GagalKeranjang as exc:
            return respons_gagal(exc)
        return respons_keranjang(keranjang, status.HTTP_201_CREATED)


class ItemKeranjangView(APIView):
    """PATCH/DELETE /api/keranjang/item/<id>/ — mengembalikan isi keranjang terbaru."""

    def patch(self, request, item_id):
        data = UbahJumlahSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            keranjang = layanan.ubah_jumlah(request.user, item_id, data.validated_data["jumlah"])
        except layanan.ItemTidakDitemukan:
            return _item_tidak_ditemukan()
        except layanan.GagalKeranjang as exc:
            return respons_gagal(exc)
        return respons_keranjang(keranjang)

    def delete(self, request, item_id):
        try:
            keranjang = layanan.hapus_item(request.user, item_id)
        except layanan.ItemTidakDitemukan:
            return _item_tidak_ditemukan()
        return respons_keranjang(keranjang)


def pesanan_milik(pembeli, nomor):
    pesanan = Pesanan.objects.filter(pembeli=pembeli, nomor=nomor).prefetch_related("item").first()
    if pesanan is None:
        raise NotFound("Pesanan tidak ditemukan.")
    return pesanan


class CheckoutView(APIView):
    """GET /api/pesanan/checkout/ — opsi checkout; POST — buat pesanan dan transaksi Snap (FR-09–FR-11)."""

    throttle_scope = "checkout"

    def get_throttles(self):
        # Hanya pembuatan pesanan yang dibatasi; membaca opsi checkout tidak.
        return super().get_throttles() if self.request.method == "POST" else []

    def get(self, request):
        isi = layanan.ringkasan(layanan.keranjang_milik(request.user))
        return Response(
            {
                "keranjang": data_keranjang(isi),
                "pengiriman": checkout.opsi_pengiriman(),
                "batas_bayar_menit": settings.BATAS_BAYAR_MENIT,
                "metode_pembayaran": list(settings.MIDTRANS_ENABLED_PAYMENTS),
            }
        )

    def post(self, request):
        data = CheckoutSerializer(data=request.data, context={"pembeli": request.user})
        data.is_valid(raise_exception=True)
        try:
            pesanan = checkout.buat_pesanan(request.user, data.validated_data)
        except checkout.GagalCheckout as exc:
            return respons_gagal(exc)
        except checkout.PembayaranTidakTersedia as exc:
            if exc.belum_dikonfigurasi:
                return Response(
                    {
                        "detail": "Pembayaran belum bisa diproses karena konfigurasi Midtrans belum lengkap. "
                        "Hubungi admin."
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            return Response(
                {
                    "detail": "Halaman pembayaran Midtrans belum bisa dibuat. Keranjang dan stok tidak berubah; "
                    "coba lagi beberapa saat."
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(PesananDetailSerializer(pesanan).data, status=status.HTTP_201_CREATED)


class HalamanPesanan(PageNumberPagination):
    page_size = 10
    invalid_page_message = "Halaman tidak ditemukan."


class DaftarPesananView(generics.ListAPIView):
    """GET /api/pesanan/ — riwayat pesanan pembeli, terbaru lebih dulu (FR-12)."""

    serializer_class = PesananRingkasSerializer
    pagination_class = HalamanPesanan

    def get_queryset(self):
        return Pesanan.objects.filter(pembeli=self.request.user).prefetch_related("item").order_by("-dibuat", "-pk")


class DetailPesananView(APIView):
    """GET /api/pesanan/<nomor>/ — detail pesanan milik pembeli (FR-12)."""

    def get(self, request, nomor):
        return Response(PesananDetailSerializer(pesanan_milik(request.user, nomor)).data)


class CekStatusPesananView(APIView):
    """POST /api/pesanan/<nomor>/cek-status/ — tanyakan status pembayaran ke Status API Midtrans.

    Dipakai setelah popup Snap ditutup atau bila notifikasi (webhook) tidak sampai. Hasil dari peramban
    (callback Snap) tidak pernah dipercaya; status selalu dibaca server dari Midtrans.
    """

    throttle_scope = "cek_status"

    def post(self, request, nomor):
        pesanan = pesanan_milik(request.user, nomor)
        if pesanan.status_pembayaran == Pesanan.StatusPembayaran.MENUNGGU:
            try:
                pembayaran.sinkronkan(pesanan.nomor)
            except midtrans.GagalMidtrans as exc:
                logger.warning("Cek status pesanan %s gagal: %s", pesanan.nomor, exc)
                return Response(
                    {"detail": "Status pembayaran belum bisa diperiksa ke Midtrans. Coba lagi beberapa saat."},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            pesanan = pesanan_milik(request.user, nomor)
        return Response(PesananDetailSerializer(pesanan).data)


class NotifikasiMidtransView(APIView):
    """POST /api/pembayaran/midtrans/notifikasi/ — Payment Notification URL di dashboard Midtrans.

    Setiap notifikasi diarsipkan di LogNotifikasiMidtrans, termasuk yang tanda tangannya tidak valid.
    Isi notifikasi tidak langsung dipercaya: setelah tanda tangan cocok, status dibaca ulang dari
    Status API Midtrans (apps.orders.pembayaran).
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]
    throttle_scope = "notifikasi_midtrans"

    def post(self, request):
        data = request.data
        if not isinstance(data, dict):
            return Response({"detail": "Isi notifikasi harus berupa objek JSON."}, status=status.HTTP_400_BAD_REQUEST)
        order_id = str(data.get("order_id") or "")[:64]
        valid = midtrans.tanda_tangan_valid(data)
        pesanan = Pesanan.objects.filter(nomor=order_id).first() if order_id else None
        LogNotifikasiMidtrans.objects.create(
            pesanan=pesanan,
            order_id=order_id,
            transaction_status=str(data.get("transaction_status") or "")[:32],
            signature_valid=valid,
            payload=data,
        )
        if not valid:
            logger.warning("Notifikasi Midtrans ditolak: tanda tangan tidak valid (order_id %r).", order_id)
            return Response({"detail": "Tanda tangan notifikasi tidak valid."}, status=status.HTTP_403_FORBIDDEN)
        if pesanan is None:
            # Misalnya notifikasi uji dari dashboard Midtrans: diarsipkan saja, tidak perlu dikirim ulang.
            return Response({"detail": "Pesanan tidak dikenal; notifikasi diarsipkan."})
        try:
            pembayaran.sinkronkan(pesanan.nomor)
        except midtrans.GagalMidtrans as exc:
            logger.warning("Notifikasi pesanan %s belum bisa dikonfirmasi ke Status API: %s", pesanan.nomor, exc)
            # Dengan 503, Midtrans mengirim ulang notifikasi beberapa kali.
            return Response(
                {"detail": "Status pembayaran belum bisa dikonfirmasi; kirim ulang nanti."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"detail": "Notifikasi diterima."})
