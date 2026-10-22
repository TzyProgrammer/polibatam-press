from django.conf import settings
from django.core.checks import Warning, register

# Midtrans: kedaluwarsa transaksi Snap maksimal 7 hari.
BATAS_BAYAR_MAKS = 7 * 24 * 60


@register()
def periksa_pengaturan_pembayaran(app_configs, **kwargs):
    """Peringatan saat startup bila pengaturan Midtrans atau checkout di .env belum siap."""
    peringatan = []
    if not settings.MIDTRANS_SERVER_KEY:
        peringatan.append(
            Warning(
                "MIDTRANS_SERVER_KEY belum diisi di .env.",
                hint="Checkout tidak bisa membuat pembayaran dan semua notifikasi Midtrans ditolak "
                "sampai server key sandbox diisi.",
                id="orders.W001",
            )
        )
    if not settings.MIDTRANS_CLIENT_KEY:
        peringatan.append(
            Warning(
                "MIDTRANS_CLIENT_KEY belum diisi di .env.",
                hint="Frontend tidak bisa membuka popup pembayaran Snap.",
                id="orders.W002",
            )
        )
    if settings.MIDTRANS_IS_PRODUCTION:
        peringatan.append(
            Warning(
                "MIDTRANS_IS_PRODUCTION=True: pembayaran memakai uang sungguhan.",
                hint="Proyek ini proof of concept; gunakan sandbox (False) kecuali memang siap rilis.",
                id="orders.W003",
            )
        )
    if not 1 <= settings.BATAS_BAYAR_MENIT <= BATAS_BAYAR_MAKS:
        peringatan.append(
            Warning(
                f"BATAS_BAYAR_MENIT harus antara 1 dan {BATAS_BAYAR_MAKS} menit (batas Midtrans 7 hari).",
                id="orders.W004",
            )
        )
    if settings.ONGKIR_KOTA_BATAM < 0:
        peringatan.append(Warning("ONGKIR_KOTA_BATAM tidak boleh negatif.", id="orders.W005"))
    return peringatan
