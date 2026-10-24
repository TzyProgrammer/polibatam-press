// Pembungkus fetch untuk API backend (/api, diteruskan Vite atau Nginx ke Django).
// - Menambahkan access token bila pengguna sudah masuk.
// - Bila backend menjawab 401 dengan code "token_not_valid", access token diperbarui sekali lewat
//   refresh token lalu permintaan diulang. Bila refresh gagal, sesi dianggap berakhir.
// - Semua kegagalan dilempar sebagai GalatApi dengan pesan berbahasa Indonesia.

const BASIS = '/api'

let sesi = {
  akses: () => null,
  segarkan: async () => false,
  habis: () => {},
}

// Dipanggil sekali dari main.js agar klien tidak perlu mengimpor store (menghindari impor melingkar).
export function aturSesi(penyedia) {
  sesi = { ...sesi, ...penyedia }
}

function pesanBawaan(status) {
  if (status === 0) return 'Tidak dapat terhubung ke server. Periksa koneksi Anda lalu coba lagi.'
  if (status === 401) return 'Sesi Anda sudah berakhir. Silakan masuk kembali.'
  if (status === 403) return 'Anda tidak memiliki akses ke data ini.'
  if (status === 404) return 'Data tidak ditemukan.'
  if (status === 429) return 'Terlalu banyak permintaan. Coba lagi beberapa saat lagi.'
  if (status === 502 || status === 503 || status === 504) {
    return 'Server sedang tidak dapat dihubungi. Coba lagi beberapa saat lagi.'
  }
  if (status >= 500) return `Terjadi gangguan pada server (${status}). Coba lagi beberapa saat lagi.`
  return 'Permintaan tidak dapat diproses.'
}

function galatIsian(data) {
  const hasil = {}
  if (!data || typeof data !== 'object' || Array.isArray(data)) return hasil
  for (const [kunci, nilai] of Object.entries(data)) {
    if (['detail', 'code', 'non_field_errors'].includes(kunci)) continue
    if (Array.isArray(nilai)) hasil[kunci] = nilai.map(String).join(' ')
    else if (typeof nilai === 'string') hasil[kunci] = nilai
  }
  return hasil
}

export class GalatApi extends Error {
  constructor(status, data) {
    const isian = galatIsian(data)
    let detail = ''
    if (data && typeof data === 'object') {
      if (typeof data.detail === 'string') detail = data.detail
      else if (Array.isArray(data.non_field_errors)) detail = data.non_field_errors.join(' ')
    }
    super(detail || Object.values(isian).join(' ') || pesanBawaan(status))
    this.name = 'GalatApi'
    this.status = status
    this.data = data
    this.detail = this.message
    this.isian = isian
  }
}

function buatUrl(path, query) {
  const url = new URL(BASIS + path, window.location.origin)
  for (const [kunci, nilai] of Object.entries(query || {})) {
    if (nilai !== undefined && nilai !== null && nilai !== '') url.searchParams.set(kunci, nilai)
  }
  return url.pathname + url.search
}

async function kirim(path, { method = 'GET', body, query, tanpaToken = false }) {
  const headers = { Accept: 'application/json' }
  let isi = body
  if (body !== undefined && !(body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
    isi = JSON.stringify(body)
  }
  const akses = tanpaToken ? null : sesi.akses()
  if (akses) headers.Authorization = `Bearer ${akses}`
  try {
    const respons = await fetch(buatUrl(path, query), { method, headers, body: isi })
    return { respons, denganToken: Boolean(akses) }
  } catch {
    throw new GalatApi(0, null)
  }
}

async function bacaJson(respons) {
  if (respons.status === 204) return null
  if (!(respons.headers.get('Content-Type') || '').includes('application/json')) return null
  try {
    return await respons.json()
  } catch {
    return null
  }
}

export async function permintaan(path, opsi = {}) {
  let { respons, denganToken } = await kirim(path, opsi)
  if (respons.status === 401 && denganToken) {
    const data = await bacaJson(respons)
    if (data?.code !== 'token_not_valid') throw new GalatApi(401, data)
    if (!(await sesi.segarkan())) {
      sesi.habis()
      throw new GalatApi(401, null)
    }
    ;({ respons } = await kirim(path, opsi))
  }
  const data = await bacaJson(respons)
  if (!respons.ok) {
    if (respons.status === 401 && !opsi.tanpaToken) sesi.habis()
    throw new GalatApi(respons.status, data)
  }
  return data
}

export const api = {
  get: (path, query) => permintaan(path, { query }),
  post: (path, body, opsi = {}) => permintaan(path, { method: 'POST', body, ...opsi }),
  patch: (path, body) => permintaan(path, { method: 'PATCH', body }),
  hapus: (path) => permintaan(path, { method: 'DELETE' }),
}
