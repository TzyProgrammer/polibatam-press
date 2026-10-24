import { defineStore } from 'pinia'

import { api } from '../api/klien'

// Tahap H1 hanya memakai jumlah item (lencana di header) dan tambah item dari halaman detail buku.
// Isi keranjang lengkap ditampilkan di Tahap H2.
export const useKeranjangStore = defineStore('keranjang', {
  state: () => ({
    jumlahItem: 0,
  }),

  actions: {
    async muat() {
      try {
        const data = await api.get('/keranjang/')
        this.jumlahItem = data.jumlah_item
      } catch {
        // Lencana tidak penting: biarkan angka terakhir.
      }
    },

    async tambah(produkId, jumlah = 1) {
      const data = await api.post('/keranjang/item/', { produk_id: produkId, jumlah })
      this.jumlahItem = data.jumlah_item
      return data
    },

    kosongkan() {
      this.jumlahItem = 0
    },
  },
})
