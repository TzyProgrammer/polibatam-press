import { defineStore } from 'pinia'

// Pesan singkat (toast) di pojok layar, misalnya "ditambahkan ke keranjang".
let nomor = 0

export const usePesanStore = defineStore('pesan', {
  state: () => ({
    daftar: [],
  }),

  actions: {
    tampilkan(teks, { jenis = 'info', tautan = null, durasi = 6000 } = {}) {
      const pesan = { id: ++nomor, teks, jenis, tautan }
      this.daftar = [...this.daftar.slice(-2), pesan]
      if (durasi) setTimeout(() => this.tutup(pesan.id), durasi)
    },

    tutup(id) {
      this.daftar = this.daftar.filter((pesan) => pesan.id !== id)
    },
  },
})
