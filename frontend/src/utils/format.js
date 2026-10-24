const RUPIAH = new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 })

export function formatRupiah(nilai) {
  return RUPIAH.format(Number(nilai) || 0)
}

const FORMAT_SINGKAT = { cetak: 'Cetak', ebook: 'Ebook', audiobook: 'Audiobook' }

export function labelFormatSingkat(format) {
  return FORMAT_SINGKAT[format] || format
}
