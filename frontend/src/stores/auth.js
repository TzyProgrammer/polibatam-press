import { defineStore } from 'pinia'

import { api, permintaan } from '../api/klien'

// Access token hanya disimpan di memori (hilang saat halaman dimuat ulang). Refresh token disimpan di
// sessionStorage agar sesi bertahan saat halaman dimuat ulang, tetapi hilang saat tab ditutup.
// Backend merotasi refresh token di setiap pemakaian dan mem-blacklist yang lama.
const KUNCI_REFRESH = 'polibatam-press.refresh'

function bacaRefresh() {
  try {
    return sessionStorage.getItem(KUNCI_REFRESH)
  } catch {
    return null
  }
}

function simpanRefresh(token) {
  try {
    if (token) sessionStorage.setItem(KUNCI_REFRESH, token)
    else sessionStorage.removeItem(KUNCI_REFRESH)
  } catch {
    // sessionStorage tidak tersedia (mode privat ketat): sesi hanya bertahan selama halaman terbuka.
  }
}

let janjiSiap = null
let janjiSegar = null

// Waktu kedaluwarsa (detik Unix) dari isi JWT. Hanya dibaca untuk menjadwalkan refresh, bukan diverifikasi:
// keabsahan token tetap diperiksa backend.
function kedaluwarsaJwt(token) {
  try {
    const isi = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    return JSON.parse(atob(isi)).exp || 0
  } catch {
    return 0
  }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    pengguna: null,
    akses: null,
  }),

  getters: {
    sudahMasuk: (state) => Boolean(state.pengguna && state.akses),
    inisial: (state) => {
      const kata = (state.pengguna?.nama_lengkap || '').trim().split(/\s+/).filter(Boolean)
      return kata.slice(0, 2).map((k) => k[0].toUpperCase()).join('') || '?'
    },
  },

  actions: {
    // Dipanggil penjaga router sebelum navigasi pertama: memulihkan sesi dari refresh token.
    pastikanSiap() {
      if (!janjiSiap) janjiSiap = this.pulihkan()
      return janjiSiap
    },

    async pulihkan() {
      if (!bacaRefresh() || !(await this.segarkanAkses())) return
      try {
        this.pengguna = await api.get('/auth/profil/')
      } catch {
        this.bersihkan()
      }
    },

    // Satu permintaan refresh untuk semua pemanggil yang bersamaan: refresh token lama langsung
    // di-blacklist backend, jadi tidak boleh dipakai dua kali.
    segarkanAkses() {
      if (!janjiSegar) {
        janjiSegar = (async () => {
          const refresh = bacaRefresh()
          if (!refresh) return false
          try {
            const data = await permintaan('/auth/refresh/', { method: 'POST', body: { refresh }, tanpaToken: true })
            this.akses = data.access
            simpanRefresh(data.refresh || refresh)
            return true
          } catch (galat) {
            if (galat.status === 400 || galat.status === 401) this.bersihkan()
            return false
          } finally {
            janjiSegar = null
          }
        })()
      }
      return janjiSegar
    },

    // Access token yang masih berlaku minimal `sisaDetik` lagi, untuk permintaan di luar klien API
    // (misalnya playlist dan kunci audiobook yang diminta hls.js). Disegarkan dulu bila hampir habis.
    async aksesSegar(sisaDetik = 30) {
      if (this.akses && kedaluwarsaJwt(this.akses) - Date.now() / 1000 > sisaDetik) return this.akses
      return (await this.segarkanAkses()) ? this.akses : null
    },

    async masukDengan(email, password) {
      const data = await api.post('/auth/login/', { email, password }, { tanpaToken: true })
      this.akses = data.access
      simpanRefresh(data.refresh)
      this.pengguna = data.pengguna
    },

    // Hanya membuat akun. Pembeli lalu masuk sendiri di halaman Masuk (revisi Tahap R: tanpa login otomatis).
    async daftar(isian) {
      return api.post('/auth/registrasi/', isian, { tanpaToken: true })
    },

    async perbaruiProfil(isian) {
      this.pengguna = await api.patch('/auth/profil/', isian)
    },

    // Profil terbaru dari server (misalnya setelah checkout menyimpan alamat ke profil). Kegagalan diabaikan.
    async muatProfil() {
      try {
        this.pengguna = await api.get('/auth/profil/')
      } catch {
        // Data lama tetap dipakai; halaman Profil memuat ulang sendiri saat dibuka.
      }
    },

    // Ubah kata sandi: backend mengeluarkan semua sesi lain lalu memberi pasangan token baru untuk perangkat ini.
    async ubahSandi(passwordLama, passwordBaru) {
      const data = await api.post('/auth/ubah-sandi/', { password_lama: passwordLama, password_baru: passwordBaru })
      this.akses = data.access
      simpanRefresh(data.refresh)
      return data
    },

    // Logout mem-blacklist refresh token terbaru. Access token disegarkan dulu agar yang dikirim
    // benar-benar refresh token terakhir hasil rotasi.
    async keluar() {
      try {
        if (bacaRefresh() && (await this.segarkanAkses())) {
          await permintaan('/auth/logout/', { method: 'POST', body: { refresh: bacaRefresh() } })
        }
      } catch {
        // Token sudah tidak berlaku di server: cukup hapus dari peramban.
      }
      this.bersihkan()
    },

    bersihkan() {
      this.akses = null
      this.pengguna = null
      simpanRefresh(null)
    },
  },
})
