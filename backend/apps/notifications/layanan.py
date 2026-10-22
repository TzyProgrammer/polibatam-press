"""Notifikasi di dalam aplikasi (ikon lonceng). Email dan WhatsApp belum dikirim (pengembangan lanjutan).

Setiap kejadian punya satu fungsi di sini agar kalimatnya seragam. Fungsi dipanggil di dalam transaksi
yang mengubah status, sehingga notifikasi ikut batal bila perubahan status batal.
`tautan` adalah path halaman frontend: /pesanan/<nomor>, /koleksi, /isbn/<id>.
"""

from django.conf import settings

from .models import Notifikasi

Kategori = Notifikasi.Kategori


def kirim(penerima, kategori, judul, pesan, tautan=""):
    return Notifikasi.objects.create(
        penerima=penerima, kategori=kategori, judul=judul[:150], pesan=pesan, tautan=tautan[:255]
    )


def _tautan_pesanan(pesanan):
    return f"/pesanan/{pesanan.nomor}"


def pembayaran_lunas(pesanan):
    kalimat = [f"Pesanan {pesanan.nomor} sudah lunas."]
    if any(item.format != "cetak" for item in pesanan.item.all()):
        kalimat.append("Ebook dan audiobook bisa dibuka di Koleksi.")
    if pesanan.metode_pengiriman == pesanan.MetodePengiriman.DELIVERY:
        kalimat.append("Buku cetak sedang diproses untuk dikirim.")
    elif pesanan.metode_pengiriman == pesanan.MetodePengiriman.TAKEAWAY:
        kalimat.append("Buku cetak sedang disiapkan; kami kabari saat siap diambil.")
    return kirim(pesanan.pembeli, Kategori.PESANAN, "Pembayaran diterima", " ".join(kalimat), _tautan_pesanan(pesanan))


def pesanan_ditutup(pesanan):
    status = pesanan.StatusPembayaran
    isi = {
        status.KEDALUWARSA: ("Pesanan kedaluwarsa", f"Pesanan {pesanan.nomor} tidak dibayar sampai batas waktu."),
        status.DIBATALKAN: ("Pesanan dibatalkan", f"Pembayaran pesanan {pesanan.nomor} dibatalkan."),
        status.GAGAL: ("Pembayaran gagal", f"Pembayaran pesanan {pesanan.nomor} gagal."),
    }.get(pesanan.status_pembayaran)
    if isi is None:
        return None
    judul, pesan = isi
    pesan += " Silakan pesan ulang bila masih berminat."
    return kirim(pesanan.pembeli, Kategori.PESANAN, judul, pesan, _tautan_pesanan(pesanan))


def pengiriman_berubah(pesanan):
    status = pesanan.StatusPengiriman
    nomor = pesanan.nomor
    isi = {
        status.DIPROSES: ("Pesanan diproses", f"Buku cetak pada pesanan {nomor} sedang diproses."),
        status.DIKIRIM: ("Pesanan dikirim", f"Buku cetak pada pesanan {nomor} sedang dikirim ke alamat Anda."),
        status.SIAP_DIAMBIL: (
            "Pesanan siap diambil",
            f"Buku cetak pada pesanan {nomor} siap diambil di {settings.LOKASI_TAKEAWAY}. "
            "Tunjukkan nomor pesanan saat mengambil.",
        ),
        status.SELESAI: (
            "Pesanan selesai",
            f"Pesanan {nomor} selesai. Terima kasih telah berbelanja di Polibatam Press.",
        ),
    }.get(pesanan.status_pengiriman)
    if isi is None:
        return None
    judul, pesan = isi
    return kirim(pesanan.pembeli, Kategori.PESANAN, judul, pesan, _tautan_pesanan(pesanan))


def hak_akses_berubah(hak):
    nama = f"{hak.produk.buku.judul} ({hak.produk.get_format_display()})"
    if hak.aktif:
        judul, pesan = "Akses konten aktif kembali", f"Akses Anda ke {nama} sudah aktif kembali."
    else:
        judul = "Akses konten dinonaktifkan"
        pesan = f"Akses Anda ke {nama} dinonaktifkan admin. Hubungi Polibatam Press bila ada pertanyaan."
    return kirim(hak.pembeli, Kategori.KONTEN, judul, pesan, "/koleksi")


def isbn_diajukan(pengajuan):
    return kirim(
        pengajuan.pemohon,
        Kategori.ISBN,
        "Pengajuan ISBN diterima",
        f"Naskah \"{pengajuan.judul}\" menunggu verifikasi admin Polibatam Press.",
        f"/isbn/{pengajuan.pk}",
    )


def isbn_status_berubah(pengajuan):
    status = pengajuan.Status
    judul_naskah = f"\"{pengajuan.judul}\""
    isi = {
        status.MENUNGGU_VERIFIKASI: (
            "Pengajuan ISBN menunggu verifikasi",
            f"Naskah {judul_naskah} menunggu verifikasi.",
        ),
        status.DIPROSES: (
            "Pengajuan ISBN diproses",
            f"Naskah {judul_naskah} lolos verifikasi dan sedang diajukan ke Perpusnas.",
        ),
        status.SELESAI: ("ISBN sudah terbit", f"Nomor ISBN untuk naskah {judul_naskah}: {pengajuan.nomor_isbn}."),
        status.DITOLAK: (
            "Pengajuan ISBN ditolak",
            f"Pengajuan untuk naskah {judul_naskah} ditolak. Alasan: {pengajuan.alasan_penolakan.strip()}",
        ),
    }.get(pengajuan.status)
    if isi is None:
        return None
    judul, pesan = isi
    return kirim(pengajuan.pemohon, Kategori.ISBN, judul, pesan, f"/isbn/{pengajuan.pk}")
