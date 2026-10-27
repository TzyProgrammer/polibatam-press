"""Watermark dinamis untuk salinan ebook (PDF) milik satu pembeli, dan pembacaan kembali kodenya.

Setiap halaman diberi tiga lapis tanda:
1. Teks diagonal semi-transparan tiga baris: "Properti Milik Polibatam Press", "Dibeli Oleh <nama pembeli>",
   lalu email yang disamarkan dan nomor pesanan.
2. Footer: identitas penerbit, kode unik, dan tanggal pembelian.
3. Teks tak terlihat (render mode 3) berisi kode, tetap terbaca oleh ekstraksi teks.
Kode juga disimpan di metadata PDF (/PolibatamPressKode, /PolibatamPressPesanan, /PolibatamPressPenerbit).

Bagian penerbit sama di semua salinan; bagian pembeli (nama, email, pesanan, kode) berbeda untuk setiap
pembelian, sehingga setiap salinan unik dan bisa dilacak.
"""

import inspect
import io
import logging
import math
import re
from dataclasses import dataclass

from pypdf import PdfReader, PdfWriter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)

PENERBIT = "Polibatam Press"
META_KODE = "/PolibatamPressKode"
META_PESANAN = "/PolibatamPressPesanan"
META_PENERBIT = "/PolibatamPressPenerbit"
AWALAN_KODE = "PolibatamPressKode:"
# Kode di teks halaman selalu didahului "Kode " (footer) atau AWALAN_KODE (teks tak terlihat),
# agar deretan heksadesimal lain di isi buku tidak ikut terbaca sebagai kode.
POLA_KODE_DI_TEKS = re.compile(r"(?:PolibatamPressKode:|Kode)\s*([0-9A-F]{4}(?:-[0-9A-F]{4}){3})(?![0-9A-F])")
HURUF_DIAGONAL = "Helvetica-Bold"
HURUF_BIASA = "Helvetica"


class GagalWatermark(Exception):
    """Kesalahan yang pesannya aman ditampilkan ke admin."""


class _GagalPemadatan(Exception):
    """Pemadatan objek kembar gagal; watermark diulang tanpa langkah itu."""


@dataclass(frozen=True)
class IdentitasPembelian:
    kode: str
    nama: str
    email_samaran: str
    nomor_pesanan: str
    tanggal: str  # tanggal pembelian, contoh 22-10-2026


@dataclass(frozen=True)
class KodeTerbaca:
    kode_metadata: str | None
    kode_teks: tuple[str, ...]  # kode unik dari teks halaman, urut kemunculan
    halaman_diperiksa: int
    jumlah_halaman: int


def samarkan_email(email):
    """budi.santoso@gmail.com → bu***@gmail.com"""
    lokal, _, domain = email.partition("@")
    tampil = lokal[:2] if len(lokal) > 2 else lokal[:1]
    return f"{tampil}***@{domain}" if domain else f"{tampil}***"


def _teks_aman(teks):
    """Huruf standar PDF (Helvetica) hanya mendukung WinAnsi; karakter lain diganti '?'."""
    return teks.encode("cp1252", "replace").decode("cp1252")


def baca_pdf(data):
    if not data.startswith(b"%PDF-"):
        raise GagalWatermark("Berkas bukan PDF.")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise GagalWatermark("PDF terkunci kata sandi; unggah PDF tanpa kata sandi pembuka.")
        jumlah = len(reader.pages)
    except GagalWatermark:
        raise
    except Exception as exc:  # berkas unggahan bisa rusak dengan berbagai cara
        raise GagalWatermark(f"PDF tidak dapat dibaca ({type(exc).__name__}).") from exc
    if jumlah == 0:
        raise GagalWatermark("PDF tidak memiliki halaman.")
    return reader


def _ukuran_muat(teks, huruf, lebar_tersedia, minimum, maksimum):
    lebar_satuan = stringWidth(teks, huruf, 1) or 1
    return max(minimum, min(maksimum, lebar_tersedia / lebar_satuan))


def _buat_lapisan(kotak, identitas):
    """Satu halaman PDF transparan berisi tanda, digambar pada koordinat kotak (cropbox) halaman."""
    kiri, bawah, kanan, atas = kotak
    lebar, tinggi = kanan - kiri, atas - bawah
    baris_penerbit = _teks_aman(f"Properti Milik {PENERBIT}")
    baris_pembeli = _teks_aman(f"Dibeli Oleh {identitas.nama}")
    baris_pesanan = _teks_aman(f"{identitas.email_samaran} · {identitas.nomor_pesanan}")
    footer = _teks_aman(
        f"{PENERBIT} · Salinan pribadi · Kode {identitas.kode} · Dibeli {identitas.tanggal} · Dilarang menyebarluaskan"
    )

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(max(kanan, 1), max(atas, 1)))

    # 1. Diagonal di tengah halaman, searah diagonal kiri-bawah ke kanan-atas, tiga baris:
    #    "Properti Milik Polibatam Press" / "Dibeli Oleh <nama>" / email samaran · nomor pesanan.
    #    Baris pembeli paling besar; ukurannya menyesuaikan panjang nama agar tetap muat di halaman.
    diagonal = math.hypot(lebar, tinggi)
    ukuran = _ukuran_muat(baris_pembeli, HURUF_DIAGONAL, 0.62 * diagonal, 10, 40)
    ukuran_penerbit = _ukuran_muat(baris_penerbit, HURUF_DIAGONAL, 0.62 * diagonal, 7, ukuran * 0.62)
    ukuran_pesanan = _ukuran_muat(baris_pesanan, HURUF_BIASA, 0.7 * diagonal, 7, ukuran * 0.6)
    c.saveState()
    c.translate(kiri + lebar / 2, bawah + tinggi / 2)
    c.rotate(math.degrees(math.atan2(tinggi, lebar)))
    # Baris penerbit berwarna biru tua Polibatam, di atas identitas pembeli yang berwarna abu-abu.
    c.setFillColorRGB(0.118, 0.216, 0.424)
    c.setFillAlpha(0.2)
    c.setFont(HURUF_DIAGONAL, ukuran_penerbit)
    c.drawCentredString(0, ukuran * 1.15 + ukuran_penerbit * 0.25, baris_penerbit)
    c.setFillColorRGB(0.45, 0.45, 0.45)
    c.setFillAlpha(0.18)
    c.setFont(HURUF_DIAGONAL, ukuran)
    c.drawCentredString(0, ukuran * 0.2, baris_pembeli)
    c.setFont(HURUF_BIASA, ukuran_pesanan)
    c.drawCentredString(0, -ukuran_pesanan * 1.3, baris_pesanan)
    c.restoreState()

    # 2. Footer.
    ukuran_footer = _ukuran_muat(footer, HURUF_BIASA, lebar - 24, 4, 7)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.setFillAlpha(0.85)
    c.setFont(HURUF_BIASA, ukuran_footer)
    c.drawCentredString(kiri + lebar / 2, bawah + max(6, min(14, tinggi * 0.015)), footer)

    # 3. Teks tak terlihat berisi kode.
    teks = c.beginText(kiri + 12, atas - 12)
    teks.setTextRenderMode(3)
    teks.setFont(HURUF_BIASA, 6)
    teks.textLine(f"{AWALAN_KODE}{identitas.kode}")
    c.drawText(teks)

    c.showPage()
    c.save()
    return PdfReader(io.BytesIO(buffer.getvalue())).pages[0]


# Nama argumen compress_identical_objects berganti di pypdf baru (yang lama dihapus di pypdf 7).
_ARGUMEN_PEMADATAN = (
    {"remove_duplicates": True, "remove_unreferenced": True}
    if "remove_duplicates" in inspect.signature(PdfWriter.compress_identical_objects).parameters
    else {"remove_identicals": True, "remove_orphans": True}
)


def beri_watermark(data, identitas):
    """Mengembalikan bytes PDF baru ber-watermark; PDF asli tidak berubah.

    Objek kembar (misalnya huruf watermark di setiap halaman) dipadatkan agar ukuran berkas tidak membengkak.
    Pemadatan itu membuka (decode) setiap stream untuk dibandingkan. Stream yang tidak bisa dibuka di server
    — misalnya gambar JBIG2 di PDF hasil pindai, yang dekodernya (jbig2dec) berlisensi AGPL dan sengaja tidak
    dipasang — membuat langkah itu gagal. Dalam hal itu watermark diulang dari awal tanpa pemadatan, sehingga
    isi gambar disalin apa adanya. Peramban tetap bisa menampilkannya (PDF.js punya dekoder JBIG2 sendiri).
    """
    try:
        return _tulis_watermark(data, identitas, padatkan=True)
    except _GagalPemadatan as exc:
        logger.info("Pemadatan PDF dilewati untuk salinan %s: %s", identitas.kode, exc.__cause__)
        return _tulis_watermark(data, identitas, padatkan=False)


def _tulis_watermark(data, identitas, padatkan):
    reader = baca_pdf(data)
    writer = PdfWriter(clone_from=reader)
    lapisan = {}
    for halaman in writer.pages:
        if halaman.rotation:
            # Rotasi dipindahkan ke isi halaman agar tanda tegak sesuai tampilan pembaca.
            halaman.transfer_rotation_to_content()
        kotak = halaman.cropbox
        kunci = (float(kotak.left), float(kotak.bottom), float(kotak.right), float(kotak.top))
        if kunci not in lapisan:
            lapisan[kunci] = _buat_lapisan(kunci, identitas)
        halaman.merge_page(lapisan[kunci])
        halaman.compress_content_streams()
    if padatkan:
        try:
            writer.compress_identical_objects(**_ARGUMEN_PEMADATAN)
        except Exception as exc:
            # Penulis (writer) ini bisa sudah setengah diubah, jadi dibuang dan watermark diulang.
            raise _GagalPemadatan(type(exc).__name__) from exc
    writer.add_metadata(
        {META_KODE: identitas.kode, META_PESANAN: identitas.nomor_pesanan, META_PENERBIT: PENERBIT}
    )
    keluaran = io.BytesIO()
    writer.write(keluaran)
    return keluaran.getvalue()


def baca_kode(data, maks_halaman=30):
    """Kode dari metadata dan dari teks halaman (paling banyak maks_halaman halaman pertama)."""
    reader = baca_pdf(data)
    metadata = reader.metadata or {}
    kode_metadata = str(metadata.get(META_KODE, "")).strip() or None
    kode_teks = []
    diperiksa = 0
    for halaman in reader.pages[:maks_halaman]:
        diperiksa += 1
        try:
            teks = halaman.extract_text() or ""
        except Exception:  # halaman rusak tidak menghentikan pemeriksaan halaman lain
            continue
        for kode in POLA_KODE_DI_TEKS.findall(teks):
            if kode not in kode_teks:
                kode_teks.append(kode)
    return KodeTerbaca(kode_metadata, tuple(kode_teks), diperiksa, len(reader.pages))


def verifikasi_watermark(data, identitas):
    """Memastikan hasil watermark memuat kode di metadata dan di teks halaman pertama."""
    terbaca = baca_kode(data, maks_halaman=1)
    if terbaca.kode_metadata != identitas.kode:
        raise GagalWatermark("Verifikasi gagal: kode tidak tersimpan di metadata PDF.")
    if identitas.kode not in terbaca.kode_teks:
        raise GagalWatermark("Verifikasi gagal: kode tidak terbaca dari teks halaman pertama.")
