import zipfile
from pathlib import PurePosixPath

from django.core.exceptions import ValidationError

# Batas ukuran berkas naskah yang diunggah pemohon.
UKURAN_MAKS_NASKAH_MB = 20


def normalisasi_isbn(nilai):
    return "".join(c for c in str(nilai) if c not in " -")


def validasi_isbn13(nilai):
    """ISBN-13: 13 digit, awalan 978/979, dan digit periksa (bobot 1 dan 3) benar."""
    angka = normalisasi_isbn(nilai)
    if len(angka) != 13 or not angka.isdigit():
        raise ValidationError("ISBN harus terdiri dari 13 digit (tanda hubung boleh).")
    if not angka.startswith(("978", "979")):
        raise ValidationError("ISBN-13 harus diawali 978 atau 979.")
    total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(angka[:12]))
    if (10 - total % 10) % 10 != int(angka[12]):
        raise ValidationError("Digit periksa ISBN tidak valid.")


def _isi_pdf(berkas):
    # Penanda %PDF- boleh didahului sedikit byte lain (spesifikasi PDF: dalam 1024 byte pertama).
    return b"%PDF-" in berkas.read(1024)


def _isi_docx(berkas):
    # Hanya daftar isi ZIP yang dibaca, tanpa mengekstrak isinya.
    if not zipfile.is_zipfile(berkas):
        return False
    berkas.seek(0)
    with zipfile.ZipFile(berkas) as arsip:
        isi = set(arsip.namelist())
    return {"[Content_Types].xml", "word/document.xml"} <= isi


def validasi_isi_naskah(berkas):
    """Ukuran dan isi naskah harus sesuai ekstensinya: PDF sungguhan atau dokumen Word (.docx)."""
    if berkas.size > UKURAN_MAKS_NASKAH_MB * 1024 * 1024:
        raise ValidationError(f"Ukuran naskah maksimal {UKURAN_MAKS_NASKAH_MB} MB.")
    ekstensi = PurePosixPath(berkas.name).suffix.lower()
    pemeriksa = {".pdf": _isi_pdf, ".docx": _isi_docx}.get(ekstensi)
    if pemeriksa is None:
        raise ValidationError("Naskah harus berformat PDF atau DOCX.")
    berkas.seek(0)
    try:
        sah = pemeriksa(berkas)
    except (OSError, zipfile.BadZipFile):
        sah = False
    finally:
        berkas.seek(0)
    if not sah:
        jenis = "PDF" if ekstensi == ".pdf" else "dokumen Word (.docx)"
        raise ValidationError(f"Isi berkas bukan {jenis} yang valid. Simpan ulang naskah lalu unggah kembali.")
