import { defineStore } from 'pinia'

import { api } from '../api/klien'

// Angka notifikasi belum dibaca untuk ikon lonceng, dimuat ulang berkala selama tab terlihat.
// Daftar notifikasi (panel di header dan halaman /notifikasi) memakai composables/daftarNotifikasi.js.
const JEDA_MUAT_MS = 30000
let pewaktu = null

export const useNotifikasiStore = defineStore('notifikasi', {
  state: () => ({
    belumDibaca: 0,
  }),

  actions: {
    atur(jumlah) {
      this.belumDibaca = Math.max(0, Number(jumlah) || 0)
    },

    async muat() {
      if (document.visibilityState === 'hidden') return
      try {
        const data = await api.get('/notifikasi/', { belum_dibaca: 1 })
        this.atur(data.belum_dibaca)
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
