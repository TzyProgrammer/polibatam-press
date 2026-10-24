import { defineStore } from 'pinia'

import { api } from '../api/klien'

// Angka notifikasi belum dibaca untuk ikon lonceng, dimuat ulang berkala selama tab terlihat.
// Panel daftar notifikasi dibuat di Tahap H4.
const JEDA_MUAT_MS = 30000
let pewaktu = null

export const useNotifikasiStore = defineStore('notifikasi', {
  state: () => ({
    belumDibaca: 0,
  }),

  actions: {
    async muat() {
      if (document.visibilityState === 'hidden') return
      try {
        const data = await api.get('/notifikasi/', { belum_dibaca: 1 })
        this.belumDibaca = data.belum_dibaca ?? 0
      } catch {
        // Gagal memuat angka notifikasi tidak menghalangi halaman lain.
      }
    },

    mulai() {
      this.berhenti()
      this.muat()
      pewaktu = setInterval(() => this.muat(), JEDA_MUAT_MS)
    },

    berhenti() {
      if (pewaktu) clearInterval(pewaktu)
      pewaktu = null
    },

    kosongkan() {
      this.berhenti()
      this.belumDibaca = 0
    },
  },
})
