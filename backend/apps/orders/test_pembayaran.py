"""Tes Tahap F: status pembayaran dari Midtrans (notifikasi, cek status, pemeriksaan berkala) dan admin pesanan."""

import hashlib
from datetime import datetime, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import User
from apps.catalog.models import Produk
from apps.drm.models import HakAkses, SalinanEbook
from apps.drm.tasks import buat_salinan_ebook
from apps.notifications.models import Notifikasi
from core.testing import STORAGES_MEMORI

from . import midtrans
from .models import LogNotifikasiMidtrans, Pesanan
from .tasks import periksa_pesanan_menunggu
from .testing import PENGATURAN_UJI, MidtransTiruanMixin, buat_pembeli, buat_produk_uji, data_status

KUNCI = PENGATURAN_UJI["MIDTRANS_SERVER_KEY"]
DELIVERY = {
    "metode_pengiriman": "delivery",
    "no_telepon_penerima": "0812-3456-7890",
    "alamat": "Jl. Ahmad Yani No. 1",
    "kecamatan": "Batam Kota",
}
Status = Pesanan.StatusPembayaran


def notifikasi_pembeli(pembeli):
    """(judul, pesan, tautan) notifikasi di aplikasi milik pembeli, terlama lebih dulu."""
    notifikasi = Notifikasi.objects.filter(penerima=pembeli).order_by("dibuat", "id")
    return list(notifikasi.values_list("judul", "pesan", "tautan"))


def notifikasi(pesanan, transaction_status="settlement", kunci=KUNCI, **lain):
    """Isi HTTP notification Midtrans beserta signature_key yang benar."""
    data = data_status(pesanan, transaction_status, **lain)
    teks = data["order_id"] + data["status_code"] + data["gross_amount"] + kunci
    data["signature_key"] = hashlib.sha512(teks.encode()).hexdigest()
    return data


@override_settings(STORAGES=STORAGES_MEMORI, **PENGATURAN_UJI)
class PembayaranTestCase(MidtransTiruanMixin, APITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.pembeli = buat_pembeli()
        self.cetak, self.ebook, self.audio = buat_produk_uji()

    def login(self, pengguna):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(pengguna)}")

    def buat_pesanan(self, *produk, pembeli=None, **pengiriman):
        """Pesanan lewat API keranjang + checkout. Buku cetak dibeli 2 eksemplar."""
        self.login(pembeli or self.pembeli)
        for p in produk:
            jumlah = 2 if p.format == Produk.Format.CETAK else 1
            response = self.client.post(reverse("keranjang-item"), {"produk_id": p.pk, "jumlah": jumlah}, format="json")
            self.assertEqual(response.status_code, 201, response.data)
        response = self.client.post(reverse("checkout"), pengiriman, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.client.credentials()
        return Pesanan.objects.get(nomor=response.data["nomor"])

    def kirim_notifikasi(self, data, kode=200):
        with mock.patch.object(buat_salinan_ebook, "delay") as delay, self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("midtrans-notifikasi"), data, format="json")
        self.assertEqual(response.status_code, kode, response.data)
        return response, delay

    def stok_cetak(self):
        return Produk.objects.get(pk=self.cetak.pk).stok

    def muat(self, pesanan):
        pesanan.refresh_from_db()
        return pesanan


class NotifikasiLunasTests(PembayaranTestCase):
    def test_lunas_memberi_hak_akses_dan_memproses_pengiriman(self):
        pesanan = self.buat_pesanan(self.cetak, self.ebook, self.audio, **DELIVERY)
        self.assertEqual(self.stok_cetak(), 1)
        self.midtrans.atur(pesanan, "settlement")
        _, delay = self.kirim_notifikasi(notifikasi(pesanan))

        self.muat(pesanan)
        self.assertEqual(pesanan.status_pembayaran, Status.LUNAS)
        self.assertEqual(pesanan.status_pengiriman, Pesanan.StatusPengiriman.DIPROSES)
        self.assertEqual(pesanan.dibayar_pada, datetime(2026, 10, 22, 21, 45, 12, tzinfo=ZoneInfo("Asia/Jakarta")))
        self.assertEqual(pesanan.midtrans_payment_type, "qris")
        self.assertEqual(pesanan.midtrans_transaction_id, f"trx-{pesanan.nomor}")
        self.assertEqual(self.stok_cetak(), 1)  # sudah dipesan saat checkout, tidak dikurangi lagi
        self.assertEqual(
            set(HakAkses.objects.filter(pembeli=self.pembeli).values_list("produk_id", flat=True)),
            {self.ebook.pk, self.audio.pk},
        )
        salinan = SalinanEbook.objects.get()
        delay.assert_called_once_with(salinan.pk)  # watermark ebook diantrikan setelah transaksi tersimpan
        log = LogNotifikasiMidtrans.objects.get()
        self.assertEqual((log.pesanan, log.signature_valid, log.transaction_status), (pesanan, True, "settlement"))
        self.assertEqual(self.midtrans.panggilan_status, [pesanan.nomor])  # status dikonfirmasi ke Status API
        self.assertEqual(
            notifikasi_pembeli(self.pembeli),
            [(
                "Pembayaran diterima",
                f"Pesanan {pesanan.nomor} sudah lunas. Ebook dan audiobook bisa dibuka di Koleksi. "
                "Buku cetak sedang diproses untuk dikirim.",
                f"/pesanan/{pesanan.nomor}",
            )],
        )

    def test_notifikasi_berulang_tidak_menggandakan(self):
        pesanan = self.buat_pesanan(self.ebook)
        self.midtrans.atur(pesanan, "settlement")
        self.kirim_notifikasi(notifikasi(pesanan))
        _, delay = self.kirim_notifikasi(notifikasi(pesanan))
        delay.assert_not_called()
        self.assertEqual(HakAkses.objects.count(), 1)
        self.assertEqual(SalinanEbook.objects.count(), 1)
        self.assertEqual(LogNotifikasiMidtrans.objects.count(), 2)
        self.assertEqual(self.muat(pesanan).status_pembayaran, Status.LUNAS)
        self.assertEqual(len(notifikasi_pembeli(self.pembeli)), 1)  # notifikasi lunas hanya sekali

    def test_pesanan_digital_tidak_punya_status_pengiriman(self):
        pesanan = self.buat_pesanan(self.audio)
        self.midtrans.atur(pesanan, "settlement")
        self.kirim_notifikasi(notifikasi(pesanan))
        self.assertEqual(self.muat(pesanan).status_pengiriman, Pesanan.StatusPengiriman.TIDAK_ADA)

    def test_kartu_kredit_capture(self):
        diterima = self.buat_pesanan(self.ebook)
        self.midtrans.atur(diterima, "capture", fraud_status="accept", payment_type="credit_card")
        self.kirim_notifikasi(notifikasi(diterima, "capture"))
        self.assertEqual(self.muat(diterima).status_pembayaran, Status.LUNAS)
        self.assertEqual(diterima.dibayar_pada, datetime(2026, 10, 22, 21, 40, tzinfo=ZoneInfo("Asia/Jakarta")))

        ditinjau = self.buat_pesanan(self.audio)
        self.midtrans.atur(ditinjau, "capture", fraud_status="challenge")
        self.kirim_notifikasi(notifikasi(ditinjau, "capture"))
        self.assertEqual(self.muat(ditinjau).status_pembayaran, Status.MENUNGGU)


class NotifikasiDitolakTests(PembayaranTestCase):
    def test_tanda_tangan_salah_ditolak_dan_diarsipkan(self):
        pesanan = self.buat_pesanan(self.ebook)
        self.midtrans.atur(pesanan, "settlement")
        palsu = notifikasi(pesanan, kunci="kunci-penyerang")
        diubah = {**notifikasi(pesanan), "gross_amount": "1.00"}
        for data in (palsu, diubah):
            with self.assertLogs("apps.orders.views", "WARNING"):
                response, _ = self.kirim_notifikasi(data, kode=403)
            self.assertEqual(response.data["detail"], "Tanda tangan notifikasi tidak valid.")
        self.assertEqual(self.muat(pesanan).status_pembayaran, Status.MENUNGGU)
        self.assertEqual(self.midtrans.panggilan_status, [])  # tidak ada yang dikonfirmasi
        self.assertFalse(HakAkses.objects.exists())
        self.assertEqual(list(LogNotifikasiMidtrans.objects.values_list("signature_valid", flat=True)), [False, False])
        self.assertEqual(LogNotifikasiMidtrans.objects.filter(pesanan=pesanan).count(), 2)

    @override_settings(MIDTRANS_SERVER_KEY="")
    def test_tanpa_server_key_semua_notifikasi_ditolak(self):
        pesanan = Pesanan.objects.create(pembeli=self.pembeli, total=40000)
        with self.assertLogs("apps.orders.views", "WARNING"):
            self.kirim_notifikasi(notifikasi(pesanan, kunci=""), kode=403)

    def test_isi_notifikasi_tidak_langsung_dipercaya(self):
        # Tanda tangan valid menyatakan lunas, tetapi Status API Midtrans masih pending.
        pesanan = self.buat_pesanan(self.ebook)
        self.midtrans.atur(pesanan, "pending")
        self.kirim_notifikasi(notifikasi(pesanan, "settlement"))
        self.muat(pesanan)
        self.assertEqual(pesanan.status_pembayaran, Status.MENUNGGU)
        self.assertEqual(pesanan.midtrans_payment_type, "qris")  # metode yang dipilih pembeli tetap dicatat
        self.assertFalse(HakAkses.objects.exists())

    def test_nominal_berbeda_diabaikan(self):
        pesanan = self.buat_pesanan(self.ebook)
        self.midtrans.atur(pesanan, "settlement", gross_amount="1000.00")
        with self.assertLogs("apps.orders.pembayaran", "ERROR") as log:
            self.kirim_notifikasi(notifikasi(pesanan))
        self.assertIn("gross_amount", log.output[0])
        self.assertEqual(self.muat(pesanan).status_pembayaran, Status.MENUNGGU)

    def test_pesanan_tidak_dikenal_diarsipkan(self):
        pesanan = Pesanan(nomor="PP-20261022-000000", total=50000)  # tidak disimpan
        response, _ = self.kirim_notifikasi(notifikasi(pesanan))
        self.assertEqual(response.data["detail"], "Pesanan tidak dikenal; notifikasi diarsipkan.")
        self.assertEqual(self.midtrans.panggilan_status, [])
        log = LogNotifikasiMidtrans.objects.get()
        self.assertEqual((log.order_id, log.pesanan, log.signature_valid), ("PP-20261022-000000", None, True))

    def test_status_api_gagal_minta_dikirim_ulang(self):
        pesanan = self.buat_pesanan(self.ebook)
        self.midtrans.gagal = midtrans.GagalMidtrans("Status API tidak bisa dihubungi (ConnectTimeout).")
        with self.assertLogs("apps.orders.views", "WARNING"):
            self.kirim_notifikasi(notifikasi(pesanan), kode=503)
        self.assertEqual(self.muat(pesanan).status_pembayaran, Status.MENUNGGU)

    def test_hanya_json(self):
        response = self.client.post(reverse("midtrans-notifikasi"), {"order_id": "x"})  # form, bukan JSON
        self.assertEqual(response.status_code, 415)
        self.assertEqual(self.client.post(reverse("midtrans-notifikasi"), [1, 2], format="json").status_code, 400)
        self.assertFalse(LogNotifikasiMidtrans.objects.exists())


class PembayaranGagalTests(PembayaranTestCase):
    def test_kedaluwarsa_mengembalikan_stok_sekali(self):
        pesanan = self.buat_pesanan(self.cetak, self.ebook, **DELIVERY)
        self.assertEqual(self.stok_cetak(), 1)
        self.midtrans.atur(pesanan, "expire")
        self.kirim_notifikasi(notifikasi(pesanan, "expire"))
        self.kirim_notifikasi(notifikasi(pesanan, "expire"))
        self.muat(pesanan)
        self.assertEqual(pesanan.status_pembayaran, Status.KEDALUWARSA)
        self.assertEqual(pesanan.status_pengiriman, Pesanan.StatusPengiriman.TIDAK_ADA)
        self.assertEqual(self.stok_cetak(), 3)
        self.assertFalse(HakAkses.objects.exists())
        self.assertEqual(
            notifikasi_pembeli(self.pembeli),
            [(
                "Pesanan kedaluwarsa",
                f"Pesanan {pesanan.nomor} tidak dibayar sampai batas waktu. Silakan pesan ulang bila masih berminat.",
                f"/pesanan/{pesanan.nomor}",
            )],
        )

    def test_dibatalkan_dan_ditolak(self):
        kasus = (("cancel", Status.DIBATALKAN), ("deny", Status.GAGAL), ("failure", Status.GAGAL))
        for status_midtrans, harapan in kasus:
            with self.subTest(status=status_midtrans):
                pesanan = self.buat_pesanan(self.cetak, **DELIVERY)
                self.assertEqual(self.stok_cetak(), 1)
                self.midtrans.atur(pesanan, status_midtrans)
                self.kirim_notifikasi(notifikasi(pesanan, status_midtrans))
                self.assertEqual(self.muat(pesanan).status_pembayaran, harapan)
                self.assertEqual(self.stok_cetak(), 3)
        judul = [n[0] for n in notifikasi_pembeli(self.pembeli)]
        self.assertEqual(judul, ["Pesanan dibatalkan", "Pembayaran gagal", "Pembayaran gagal"])

    def test_notifikasi_tidak_berurutan_tidak_membuat_status_mundur(self):
        pesanan = self.buat_pesanan(self.cetak, self.ebook, **DELIVERY)
        self.midtrans.atur(pesanan, "settlement")
        self.kirim_notifikasi(notifikasi(pesanan))
        for status_midtrans in ("pending", "expire", "refund"):
            self.midtrans.atur(pesanan, status_midtrans)
            with self.assertLogs("apps.orders.pembayaran", "INFO"):
                self.kirim_notifikasi(notifikasi(pesanan, status_midtrans))
        self.assertEqual(self.muat(pesanan).status_pembayaran, Status.LUNAS)
        self.assertEqual(self.stok_cetak(), 1)

    def test_dibayar_setelah_dianggap_kedaluwarsa(self):
        pesanan = self.buat_pesanan(self.cetak, self.ebook, **DELIVERY)
        self.midtrans.atur(pesanan, "expire")
        self.kirim_notifikasi(notifikasi(pesanan, "expire"))
        self.assertEqual(self.stok_cetak(), 3)
        self.midtrans.atur(pesanan, "settlement")
        with self.assertLogs("apps.orders.pembayaran", "WARNING"):
            self.kirim_notifikasi(notifikasi(pesanan))
        self.assertEqual(self.muat(pesanan).status_pembayaran, Status.LUNAS)
        self.assertEqual(pesanan.status_pengiriman, Pesanan.StatusPengiriman.DIPROSES)
        self.assertEqual(self.stok_cetak(), 1)  # stok dipesan ulang
        self.assertTrue(HakAkses.objects.filter(produk=self.ebook).exists())

    def test_dibayar_setelah_kedaluwarsa_tetapi_stok_habis(self):
        pesanan = self.buat_pesanan(self.cetak, **DELIVERY)
        self.midtrans.atur(pesanan, "expire")
        self.kirim_notifikasi(notifikasi(pesanan, "expire"))
        Produk.objects.filter(pk=self.cetak.pk).update(stok=1)  # stok terjual ke pembeli lain
        self.midtrans.atur(pesanan, "settlement")
        with self.assertLogs("apps.orders.pembayaran", "WARNING") as log:
            self.kirim_notifikasi(notifikasi(pesanan))
        self.assertTrue(any("perlu ditangani admin" in baris for baris in log.output))
        self.assertEqual(self.muat(pesanan).status_pembayaran, Status.LUNAS)
        self.assertEqual(self.stok_cetak(), 1)


class CekStatusTests(PembayaranTestCase):
    def cek(self, pesanan, kode=200):
        self.login(self.pembeli)
        with mock.patch.object(buat_salinan_ebook, "delay"), self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("pesanan-cek-status", args=[pesanan.nomor]))
        self.assertEqual(response.status_code, kode, response.data)
        return response

    def test_cek_status_setelah_membayar(self):
        pesanan = self.buat_pesanan(self.ebook)
        self.assertEqual(self.cek(pesanan).data["status_pembayaran"], "menunggu")  # belum memilih metode bayar
        self.midtrans.atur(pesanan, "settlement")
        data = self.cek(pesanan).data
        self.assertEqual((data["status_pembayaran"], data["metode_pembayaran"]), ("lunas", "qris"))
        self.assertIsNone(data["pembayaran"])
        self.assertTrue(HakAkses.objects.filter(pembeli=self.pembeli, produk=self.ebook).exists())

    def test_pesanan_selesai_tidak_ditanyakan_lagi(self):
        pesanan = self.buat_pesanan(self.ebook)
        self.midtrans.atur(pesanan, "settlement")
        self.cek(pesanan)
        self.cek(pesanan)
        self.assertEqual(self.midtrans.panggilan_status, [pesanan.nomor])

    def test_midtrans_tidak_bisa_dihubungi(self):
        pesanan = self.buat_pesanan(self.ebook)
        self.midtrans.gagal = midtrans.GagalMidtrans("Status API tidak bisa dihubungi (ConnectionError).")
        with self.assertLogs("apps.orders.views", "WARNING"):
            response = self.cek(pesanan, kode=502)
        self.assertIn("belum bisa diperiksa", response.data["detail"])


class PemeriksaanBerkalaTests(PembayaranTestCase):
    def mundurkan_batas(self, pesanan, menit):
        Pesanan.objects.filter(pk=pesanan.pk).update(batas_bayar=timezone.now() - timedelta(minutes=menit))

    def test_rekonsiliasi_pesanan_menunggu(self):
        lewat = self.buat_pesanan(self.cetak, **DELIVERY)  # pembeli tidak pernah memilih metode bayar
        self.mundurkan_batas(lewat, 6)
        baru_lewat = self.buat_pesanan(self.audio)
        self.mundurkan_batas(baru_lewat, 1)  # masih dalam margin 5 menit
        dibayar = self.buat_pesanan(self.ebook)
        self.midtrans.atur(dibayar, "settlement")  # sudah dibayar, tetapi notifikasinya tidak sampai
        self.assertEqual(self.stok_cetak(), 1)

        with mock.patch.object(buat_salinan_ebook, "delay"), self.captureOnCommitCallbacks(execute=True):
            hasil = periksa_pesanan_menunggu()
        self.assertEqual(hasil, {"kedaluwarsa": 1, "menunggu": 1, "lunas": 1})
        self.assertEqual(self.muat(lewat).status_pembayaran, Status.KEDALUWARSA)
        self.assertEqual(self.muat(baru_lewat).status_pembayaran, Status.MENUNGGU)
        self.assertEqual(self.muat(dibayar).status_pembayaran, Status.LUNAS)
        self.assertEqual(self.stok_cetak(), 3)  # stok pesanan yang kedaluwarsa kembali

    def test_midtrans_gagal_dilewati(self):
        pesanan = self.buat_pesanan(self.ebook)
        self.midtrans.gagal = midtrans.GagalMidtrans("Status API tidak bisa dihubungi (ReadTimeout).")
        with self.assertLogs("apps.orders.tasks", "WARNING"):
            self.assertEqual(periksa_pesanan_menunggu(), {"gagal_diperiksa": 1})
        self.assertEqual(self.muat(pesanan).status_pembayaran, Status.MENUNGGU)

    def test_tanpa_server_key_dihentikan(self):
        self.buat_pesanan(self.ebook)
        self.buat_pesanan(self.audio)
        self.midtrans.gagal = midtrans.BelumDikonfigurasi("MIDTRANS_SERVER_KEY belum diisi di .env.")
        with self.assertLogs("apps.orders.tasks", "WARNING") as log:
            self.assertEqual(periksa_pesanan_menunggu(), {})
        self.assertEqual(len(log.output), 1)
        self.assertEqual(len(self.midtrans.panggilan_status), 1)

    def test_terjadwal_di_celery_beat(self):
        jadwal = settings.CELERY_BEAT_SCHEDULE["periksa-pesanan-menunggu"]
        self.assertEqual(jadwal["task"], periksa_pesanan_menunggu.name)
        self.assertEqual(jadwal["schedule"], 300.0)


class AdminPesananTests(PembayaranTestCase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser(email="admin@example.com", password="x", nama_lengkap="Admin")

    def url_ubah(self, pesanan):
        return reverse("admin:orders_pesanan_change", args=[pesanan.pk])

    def lunaskan(self, pesanan):
        self.midtrans.atur(pesanan, "settlement")
        self.kirim_notifikasi(notifikasi(pesanan))
        return self.muat(pesanan)

    def simpan_di_admin(self, pesanan, **isian):
        """POST formulir ubah pesanan, termasuk data management form inline item pesanan."""
        item = list(pesanan.item.all())
        data = {"item-TOTAL_FORMS": len(item), "item-INITIAL_FORMS": len(item), "item-MIN_NUM_FORMS": 0,
                "item-MAX_NUM_FORMS": 1000, **isian}
        for nomor, baris in enumerate(item):
            data[f"item-{nomor}-id"] = baris.pk
            data[f"item-{nomor}-pesanan"] = pesanan.pk
        return self.client.post(self.url_ubah(pesanan), data)

    def test_pilihan_status_pengiriman_mengikuti_metode(self):
        delivery = self.lunaskan(self.buat_pesanan(self.cetak, **DELIVERY))
        self.assertEqual(delivery.pilihan_status_pengiriman(), ["diproses", "dikirim", "selesai"])
        Produk.objects.filter(pk=self.cetak.pk).update(stok=3)
        takeaway = self.lunaskan(
            self.buat_pesanan(self.cetak, metode_pengiriman="takeaway", no_telepon_penerima="0812-0000-1111")
        )
        self.assertEqual(takeaway.pilihan_status_pengiriman(), ["diproses", "siap_diambil", "selesai"])

        self.client.force_login(self.admin)
        halaman = self.client.get(self.url_ubah(takeaway))
        self.assertContains(halaman, 'value="siap_diambil"')
        self.assertNotContains(halaman, 'value="dikirim"')
        self.assertContains(halaman, PENGATURAN_UJI["LOKASI_TAKEAWAY"])

        ditolak = self.simpan_di_admin(delivery, status_pengiriman="siap_diambil")  # bukan alur delivery
        self.assertEqual(ditolak.status_code, 200)  # formulir ditampilkan lagi dengan error
        self.assertIn("status_pengiriman", ditolak.context["adminform"].form.errors)
        self.assertEqual(self.muat(delivery).status_pengiriman, "diproses")
        self.assertEqual(self.simpan_di_admin(delivery, status_pengiriman="dikirim").status_code, 302)
        self.assertEqual(self.muat(delivery).status_pengiriman, "dikirim")
        self.simpan_di_admin(delivery, status_pengiriman="dikirim")  # disimpan tanpa perubahan
        self.simpan_di_admin(takeaway, status_pengiriman="siap_diambil")

        judul = [n[0] for n in notifikasi_pembeli(self.pembeli)]
        self.assertEqual(
            judul, ["Pembayaran diterima", "Pembayaran diterima", "Pesanan dikirim", "Pesanan siap diambil"]
        )
        siap_diambil = notifikasi_pembeli(self.pembeli)[-1]
        self.assertIn(PENGATURAN_UJI["LOKASI_TAKEAWAY"], siap_diambil[1])
        self.assertEqual(siap_diambil[2], f"/pesanan/{takeaway.nomor}")

    def test_status_pembayaran_tidak_bisa_diubah_admin(self):
        pesanan = self.buat_pesanan(self.cetak, **DELIVERY)  # belum lunas
        self.client.force_login(self.admin)
        halaman = self.client.get(self.url_ubah(pesanan))
        self.assertNotContains(halaman, 'name="status_pengiriman"')
        self.assertNotContains(halaman, 'name="status_pembayaran"')
        self.simpan_di_admin(pesanan, status_pembayaran="lunas", status_pengiriman="dikirim")
        self.muat(pesanan)
        self.assertEqual((pesanan.status_pembayaran, pesanan.status_pengiriman), ("menunggu", "menunggu"))

    def test_pesanan_tidak_bisa_ditambah_atau_dihapus(self):
        pesanan = self.buat_pesanan(self.ebook)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("admin:orders_pesanan_add")).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:orders_pesanan_delete", args=[pesanan.pk])).status_code, 403)
        daftar = self.client.get(reverse("admin:orders_pesanan_changelist"))
        self.assertNotContains(daftar, 'value="delete_selected"')
        self.assertContains(daftar, 'value="cek_status_midtrans"')

    def test_aksi_cek_status_ke_midtrans(self):
        pesanan = self.buat_pesanan(self.ebook)
        self.midtrans.atur(pesanan, "settlement")
        self.client.force_login(self.admin)
        with mock.patch.object(buat_salinan_ebook, "delay"), self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("admin:orders_pesanan_changelist"),
                {"action": "cek_status_midtrans", "_selected_action": [pesanan.pk]},
                follow=True,
            )
        self.assertContains(response, f"{pesanan.nomor}: Lunas")
        self.assertEqual(self.muat(pesanan).status_pembayaran, Status.LUNAS)
