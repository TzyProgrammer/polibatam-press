// Posisi terakhir membaca ebook (halaman) dan mendengarkan audiobook (detik), disimpan di localStorage
// peramban ini saja sebagai kemudahan. Bukan data penting: bila penyimpanan tidak tersedia (mode privat),
// pembaca dan pemutar tetap berjalan dari awal. Token tidak pernah disimpan di sini.
const AWALAN = 'polibatam-press.posisi'

function kunci(jenis, produkId, penggunaId) {
  return `${AWALAN}.${penggunaId || 'tamu'}.${jenis}.${produkId}`
}

export function bacaPosisi(jenis, produkId, penggunaId) {
  try {
    const nilai = Number.parseFloat(localStorage.getItem(kunci(jenis, produkId, penggunaId)))
    return Number.isFinite(nilai) && nilai > 0 ? nilai : 0
  } catch {
    return 0
  }
}

export function simpanPosisi(jenis, produkId, penggunaId, nilai) {
  try {
    if (nilai > 0) localStorage.setItem(kunci(jenis, produkId, penggunaId), String(nilai))
    else localStorage.removeItem(kunci(jenis, produkId, penggunaId))
  } catch {
    // Penyimpanan penuh atau diblokir: abaikan.
  }
}
