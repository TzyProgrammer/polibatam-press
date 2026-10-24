const RUPIAH = new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 })

export function formatRupiah(nilai) {
  return RUPIAH.format(Number(nilai) || 0)
}

const FORMAT_SINGKAT = { cetak: 'Cetak', ebook: 'Ebook', audiobook: 'Audiobook' }

export function labelFormatSingkat(format) {
  return FORMAT_SINGKAT[format] || format
}

// Waktu dari API berupa ISO 8601 bertanda zona. Ditampilkan dalam WIB (Batam), apa pun zona perangkat.
const ZONA = 'Asia/Jakarta'
const TANGGAL = new Intl.DateTimeFormat('id-ID', { day: 'numeric', month: 'short', year: 'numeric', timeZone: ZONA })
const JAM = new Intl.DateTimeFormat('id-ID', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZone: ZONA })

function tanggalSah(iso) {
  if (!iso) return null
  const tanggal = new Date(iso)
  return Number.isNaN(tanggal.getTime()) ? null : tanggal
}

// "24 Okt 2026"
export function formatTanggal(iso) {
  const tanggal = tanggalSah(iso)
  return tanggal ? TANGGAL.format(tanggal) : ''
}

// "24 Okt 2026, 10.12 WIB"
export function formatTanggalJam(iso) {
  const tanggal = tanggalSah(iso)
  return tanggal ? `${TANGGAL.format(tanggal)}, ${JAM.format(tanggal)} WIB` : ''
}

// Sisa waktu bayar: "59:12" atau "1:02:05" bila lebih dari satu jam.
export function formatSisaWaktu(detik) {
  const total = Math.max(0, Math.floor(detik))
  const jam = Math.floor(total / 3600)
  const menit = Math.floor((total % 3600) / 60)
  const sisa = total % 60
  const dua = (n) => String(n).padStart(2, '0')
  return jam ? `${jam}:${dua(menit)}:${dua(sisa)}` : `${dua(menit)}:${dua(sisa)}`
}

// Kolom midtrans_payment_type: diisi dari Status API Midtrans setelah pembeli memilih metode di Snap.
const METODE_BAYAR = { qris: 'QRIS', other_qris: 'QRIS', gopay: 'GoPay', 'uji-lokal': 'Uji lokal (tanpa Midtrans)' }

export function labelMetodeBayar(kode) {
  if (!kode) return 'QRIS melalui Midtrans'
  return METODE_BAYAR[kode] || kode
}

const PENGIRIMAN_SINGKAT = { delivery: 'Delivery', takeaway: 'Takeaway', tanpa: 'Produk digital' }

export function labelPengirimanSingkat(metode) {
  return PENGIRIMAN_SINGKAT[metode] || metode
}
