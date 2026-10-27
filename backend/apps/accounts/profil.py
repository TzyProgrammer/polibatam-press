"""Data alamat di profil pembeli yang ikut diperbarui dari isian checkout (revisi Tahap R)."""

KOLOM_ALAMAT = ("no_telepon", "alamat", "kecamatan")


def perbarui_dari_checkout(pengguna, pengiriman):
    """Simpan telepon, alamat, dan kecamatan dari checkout ke profil.

    Kolom profil yang masih kosong selalu diisi. Kolom yang sudah berisi nilai lain hanya diganti bila
    pembeli menyetujuinya (simpan_ke_profil). Mengembalikan daftar kolom yang berubah.
    """
    isian = pengiriman.get("profil") or {}
    timpa = bool(pengiriman.get("simpan_ke_profil"))
    berubah = []
    for kolom in KOLOM_ALAMAT:
        nilai = (isian.get(kolom) or "").strip()
        lama = (getattr(pengguna, kolom) or "").strip()
        if not nilai or nilai == lama or (lama and not timpa):
            continue
        setattr(pengguna, kolom, nilai)
        berubah.append(kolom)
    if berubah:
        pengguna.save(update_fields=berubah)
    return berubah
