import { ref } from 'vue'

import { api } from '../api/klien'
import { useNotifikasiStore } from '../stores/notifikasi'

// Daftar notifikasi bertahap (20 per halaman API) untuk panel di header dan halaman /notifikasi.
// `hanyaBelumDibaca` berupa fungsi agar filter bisa berubah tanpa membuat ulang daftar.
export function useDaftarNotifikasi(hanyaBelumDibaca = () => false) {
  const toko = useNotifikasiStore()
  const daftar = ref(null)
  const adaLagi = ref(false)
  const memuat = ref(false)
  const galat = ref('')
  let halaman = 0
  let nomorPermintaan = 0

  async function ambil(nomorHalaman) {
    const data = await api.get('/notifikasi/', {
      page: nomorHalaman > 1 ? nomorHalaman : undefined,
      belum_dibaca: hanyaBelumDibaca() ? 1 : undefined,
    })
    toko.atur(data.belum_dibaca)
    return data
  }

  // Memuat ulang dari halaman pertama (saat panel dibuka atau filter berganti). Daftar lama dikosongkan dulu
  // agar isi filter sebelumnya tidak sempat tampil.
  async function muatAwal() {
    const nomor = ++nomorPermintaan
    daftar.value = null
    adaLagi.value = false
    memuat.value = true
    galat.value = ''
    try {
      const data = await ambil(1)
      if (nomor !== nomorPermintaan) return
      daftar.value = data.results
      halaman = 1
      adaLagi.value = Boolean(data.next)
    } catch (e) {
      if (nomor === nomorPermintaan && e.status !== 401) galat.value = e.detail
    } finally {
      if (nomor === nomorPermintaan) memuat.value = false
    }
  }

  async function muatLagi() {
    if (memuat.value || !adaLagi.value) return
    const nomor = ++nomorPermintaan
    memuat.value = true
    galat.value = ''
    try {
      const data = await ambil(halaman + 1)
      if (nomor !== nomorPermintaan) return
      // Notifikasi baru yang masuk di antara dua permintaan menggeser halaman: buang yang sudah tampil.
      const ada = new Set(daftar.value.map((n) => n.id))
      daftar.value = [...daftar.value, ...data.results.filter((n) => !ada.has(n.id))]
      halaman += 1
      adaLagi.value = Boolean(data.next)
    } catch (e) {
      if (nomor !== nomorPermintaan) return
      // Halaman berikutnya sudah tidak ada (misalnya notifikasi di filter "Belum dibaca" sudah dibaca
      // di tempat lain): anggap daftar sudah habis.
      if (e.status === 404) {
        adaLagi.value = false
        return
      }
      if (e.status !== 401) galat.value = e.detail
    } finally {
      if (nomor === nomorPermintaan) memuat.value = false
    }
  }

  // Ditandai dibaca lebih dulu di tampilan; bila permintaan gagal, dikembalikan.
  async function baca(notifikasi) {
    if (notifikasi.dibaca) return
    notifikasi.dibaca = true
    toko.atur(toko.belumDibaca - 1)
    try {
      await api.post(`/notifikasi/${notifikasi.id}/baca/`)
    } catch {
      notifikasi.dibaca = false
      toko.atur(toko.belumDibaca + 1)
    }
  }

  async function bacaSemua() {
    try {
      const data = await api.post('/notifikasi/baca-semua/')
      toko.atur(data.belum_dibaca)
      if (hanyaBelumDibaca()) daftar.value = []
      else daftar.value?.forEach((n) => (n.dibaca = true))
      adaLagi.value = hanyaBelumDibaca() ? false : adaLagi.value
    } catch (e) {
      if (e.status !== 401) galat.value = e.detail
    }
  }

  return { daftar, adaLagi, memuat, galat, muatAwal, muatLagi, baca, bacaSemua }
}
