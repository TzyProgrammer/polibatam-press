"""Lacak kebocoran ebook (FR-16): dari PDF yang diduga bocor ke pembeli dan pesanannya."""

from dataclasses import dataclass, field

from .kode import POLA_KODE, kode_cocok
from .models import SalinanEbook
from .watermark import baca_kode

ASLI = "asli"
TIDAK_TERDAFTAR = "tidak_terdaftar"
TIDAK_SAH = "tidak_sah"
FORMAT_SALAH = "format_salah"

KETERANGAN = {
    ASLI: "Asli: kode diterbitkan sistem untuk pembelian ini (HMAC cocok).",
    TIDAK_TERDAFTAR: "Palsu: kode tidak terdaftar di sistem.",
    TIDAK_SAH: "Tidak sah: kode terdaftar, tetapi hasil hitung ulang HMAC tidak cocok.",
    FORMAT_SALAH: "Bukan kode watermark Polibatam Press.",
}


@dataclass
class TemuanKode:
    kode: str
    sumber: list[str]
    status: str
    salinan: SalinanEbook | None = None

    @property
    def keterangan(self):
        return KETERANGAN[self.status]

    @property
    def asli(self):
        return self.status == ASLI


@dataclass
class HasilLacak:
    temuan: list[TemuanKode]
    halaman_diperiksa: int
    jumlah_halaman: int
    catatan: list[str] = field(default_factory=list)

    @property
    def temuan_asli(self):
        return [t for t in self.temuan if t.asli]


def periksa_kode(kode, sumber):
    if not POLA_KODE.match(kode):
        return TemuanKode(kode, sumber, FORMAT_SALAH)
    salinan = (
        SalinanEbook.objects.select_related(
            "hak_akses__pembeli", "hak_akses__produk__buku", "hak_akses__item_pesanan__pesanan"
        )
        .filter(kode_watermark=kode)
        .first()
    )
    if salinan is None:
        return TemuanKode(kode, sumber, TIDAK_TERDAFTAR)
    hak = salinan.hak_akses
    # Hitung ulang HMAC dari identitas pembelian: memastikan kode memang diterbitkan sistem
    # untuk pembeli, item pesanan, dan produk ini, bukan sekadar cocok dengan isi basis data.
    if not kode_cocok(kode, hak.pembeli_id, hak.item_pesanan_id, hak.produk_id):
        return TemuanKode(kode, sumber, TIDAK_SAH, salinan)
    return TemuanKode(kode, sumber, ASLI, salinan)


def lacak_kebocoran(data, maks_halaman=30):
    terbaca = baca_kode(data, maks_halaman=maks_halaman)
    sumber_per_kode = {}
    if terbaca.kode_metadata:
        sumber_per_kode.setdefault(terbaca.kode_metadata, []).append("metadata")
    for kode in terbaca.kode_teks:
        sumber_per_kode.setdefault(kode, []).append("teks halaman")
    temuan = [periksa_kode(kode, sumber) for kode, sumber in sumber_per_kode.items()]

    catatan = []
    if terbaca.kode_teks and not terbaca.kode_metadata:
        catatan.append("Metadata kode tidak ada (kemungkinan dihapus); kode ditemukan dari teks halaman.")
    if terbaca.kode_metadata and not terbaca.kode_teks:
        catatan.append("Kode hanya ada di metadata; teks halaman tidak memuat kode (kemungkinan dipindai ulang).")
    if terbaca.kode_metadata and terbaca.kode_teks and terbaca.kode_metadata not in terbaca.kode_teks:
        catatan.append("Kode di metadata berbeda dengan kode di teks halaman; berkas kemungkinan dimanipulasi.")
    if len({t.kode for t in temuan if t.asli}) > 1:
        catatan.append("Ditemukan lebih dari satu kode asli; berkas kemungkinan gabungan beberapa salinan.")
    return HasilLacak(temuan, terbaca.halaman_diperiksa, terbaca.jumlah_halaman, catatan)
