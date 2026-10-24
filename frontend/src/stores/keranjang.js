import { defineStore } from 'pinia'

import { api } from '../api/klien'

// Isi keranjang dari API. Setiap perubahan (tambah, ubah jumlah, hapus) dijawab backend dengan isi keranjang
// terbaru, jadi data di sini selalu mengikuti server: stok dan ketersediaan bisa berubah sejak item ditambahkan.
// isi: {item: [...], jumlah_item, total, perlu_pengiriman, semua_tersedia}
export const useKeranjangStore = defineStore('keranjang', {
  state: () => ({
    isi: null,
    jumlahItem: 0,
  }),

  actions: {
    simpan(data) {
      this.isi = data
      this.jumlahItem = data?.jumlah_item ?? 0
      return data
    },

    // Untuk halaman: melempar GalatApi bila gagal.
    async ambil() {
      return this.simpan(await api.get('/keranjang/'))
    },

    // Untuk lencana di header: kegagalan diabaikan, angka terakhir dibiarkan.
    async muat() {
      try {
        await this.ambil()
      } catch {
        // Lencana tidak penting.
      }
    },

    async tambah(produkId, jumlah = 1) {
      return this.simpan(await api.post('/keranjang/item/', { produk_id: produkId, jumlah }))
    },

    async ubahJumlah(itemId, jumlah) {
      return this.simpan(await api.patch(`/keranjang/item/${itemId}/`, { jumlah }))
    },

    async hapus(itemId) {
      return this.simpan(await api.hapus(`/keranjang/item/${itemId}/`))
    },

    kosongkan() {
      this.isi = null
      this.jumlahItem = 0
    },
  },
})
