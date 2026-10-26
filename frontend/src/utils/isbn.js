import { api } from '../api/klien'

// Alur status pengajuan ISBN (sama dengan PengajuanISBN.pilihan_status() di backend):
// menunggu verifikasi → diproses → selesai, atau ditolak di salah satu tahap.
export const KETERANGAN_ISBN = {
  menunggu_verifikasi: 'Naskah menunggu diperiksa admin Polibatam Press.',
  diproses: 'Naskah lolos verifikasi dan sedang diajukan ke Perpusnas.',
  selesai: 'ISBN sudah terbit untuk naskah ini.',
  ditolak: 'Pengajuan ditolak. Perbaiki naskah lalu kirim sebagai pengajuan baru.',
}

export const UKURAN_MAKS_NASKAH_MB = 20
export const EKSTENSI_NASKAH = ['pdf', 'docx']

// Pemeriksaan awal di peramban; isi berkas tetap diperiksa backend (validasi_isi_naskah).
export function periksaBerkasNaskah(berkas) {
  if (!berkas) return 'Pilih berkas naskah (PDF atau DOCX).'
  const ekstensi = berkas.name.includes('.') ? berkas.name.split('.').pop().toLowerCase() : ''
  if (!EKSTENSI_NASKAH.includes(ekstensi)) return 'Naskah harus berformat PDF atau DOCX.'
  if (berkas.size > UKURAN_MAKS_NASKAH_MB * 1024 * 1024) return `Ukuran naskah maksimal ${UKURAN_MAKS_NASKAH_MB} MB.`
  if (!berkas.size) return 'Berkas naskah kosong.'
  return ''
}

// Tautan unduh naskah berupa presigned URL 5 menit, jadi selalu diminta baru tepat sebelum diunduh.
// Respons bucket memakai Content-Disposition: attachment, sehingga halaman ini tidak ditinggalkan.
export async function unduhNaskah(id) {
  const data = await api.get(`/isbn/pengajuan/${id}/`)
  if (!data.naskah?.url) throw Object.assign(new Error('naskah tidak ada'), { detail: 'Berkas naskah tidak ditemukan.' })
  const tautan = document.createElement('a')
  tautan.href = data.naskah.url
  tautan.rel = 'noopener'
  document.body.append(tautan)
  tautan.click()
  tautan.remove()
  return data
}
