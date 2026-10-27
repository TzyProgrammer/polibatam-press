import { nextTick } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '../stores/auth'
import { tujuanAman } from '../utils/navigasi'
import BerandaView from '../views/BerandaView.vue'

const HalamanAuth = () => import('../views/AuthView.vue')

// meta.perluMasuk: hanya untuk pengguna yang sudah masuk. meta.tamu: hanya untuk yang belum masuk.
// meta.menu: menu header yang ditandai aktif. meta.tanpaKerangka: tanpa header dan footer situs.
const routes = [
  { path: '/', name: 'beranda', component: BerandaView, meta: { judul: 'Katalog', menu: 'katalog' } },
  {
    path: '/buku/:slug',
    name: 'buku',
    component: () => import('../views/DetailBukuView.vue'),
    meta: { judul: 'Detail buku', menu: 'katalog' },
  },
  // Masuk, Daftar, Lupa kata sandi, dan Atur ulang kata sandi memakai satu komponen (AuthView) agar perpindahan
  // antarhalaman itu bisa dianimasikan (panel formulir dan foto bertukar sisi).
  { path: '/masuk', name: 'masuk', component: HalamanAuth, meta: { judul: 'Masuk', tamu: true } },
  { path: '/daftar', name: 'daftar', component: HalamanAuth, meta: { judul: 'Daftar akun', tamu: true } },
  { path: '/lupa-sandi', name: 'lupa-sandi', component: HalamanAuth, meta: { judul: 'Lupa kata sandi', tamu: true } },
  {
    // Terbuka juga saat masuk: tautan dari email bisa dibuka di peramban yang sedang memakai akun itu.
    path: '/atur-ulang-sandi',
    name: 'atur-ulang-sandi',
    component: HalamanAuth,
    meta: { judul: 'Atur ulang kata sandi' },
  },
  {
    path: '/profil',
    name: 'profil',
    component: () => import('../views/ProfilView.vue'),
    meta: { judul: 'Profil', perluMasuk: true },
  },
  {
    path: '/keranjang',
    name: 'keranjang',
    component: () => import('../views/KeranjangView.vue'),
    meta: { judul: 'Keranjang', perluMasuk: true },
  },
  {
    path: '/checkout',
    name: 'checkout',
    component: () => import('../views/CheckoutView.vue'),
    meta: { judul: 'Checkout', perluMasuk: true },
  },
  {
    path: '/pesanan',
    name: 'pesanan',
    component: () => import('../views/RiwayatPesananView.vue'),
    meta: { judul: 'Pesanan saya', perluMasuk: true, menu: 'pesanan' },
  },
  {
    path: '/pesanan/:nomor',
    name: 'pesanan-detail',
    component: () => import('../views/DetailPesananView.vue'),
    meta: { judul: 'Detail pesanan', perluMasuk: true, menu: 'pesanan' },
  },
  {
    path: '/pesanan/:nomor/bayar',
    name: 'pembayaran',
    component: () => import('../views/PembayaranView.vue'),
    meta: { judul: 'Pembayaran', perluMasuk: true, menu: 'pesanan' },
  },
  {
    path: '/koleksi',
    name: 'koleksi',
    component: () => import('../views/KoleksiView.vue'),
    meta: { judul: 'Koleksi saya', perluMasuk: true, menu: 'koleksi' },
  },
  {
    path: '/koleksi/ebook/:produkId(\\d+)',
    name: 'baca-ebook',
    component: () => import('../views/PembacaEbookView.vue'),
    meta: { judul: 'Baca ebook', perluMasuk: true, menu: 'koleksi', tanpaKerangka: true },
  },
  {
    path: '/koleksi/audiobook/:produkId(\\d+)',
    name: 'putar-audiobook',
    component: () => import('../views/PemutarAudiobookView.vue'),
    meta: { judul: 'Dengarkan audiobook', perluMasuk: true, menu: 'koleksi' },
  },
  {
    // Terbuka untuk tamu: berisi penjelasan dan ajakan masuk; formulir dan daftar hanya setelah masuk.
    path: '/isbn',
    name: 'isbn',
    component: () => import('../views/IsbnView.vue'),
    meta: { judul: 'Pengajuan ISBN', menu: 'isbn' },
  },
  {
    path: '/isbn/:id(\\d+)',
    name: 'isbn-detail',
    component: () => import('../views/DetailIsbnView.vue'),
    meta: { judul: 'Pengajuan ISBN', perluMasuk: true, menu: 'isbn' },
  },
  {
    path: '/notifikasi',
    name: 'notifikasi',
    component: () => import('../views/NotifikasiView.vue'),
    meta: { judul: 'Notifikasi', perluMasuk: true },
  },
  {
    path: '/:jalur(.*)*',
    name: 'tidak-ditemukan',
    component: () => import('../views/TidakDitemukanView.vue'),
    meta: { judul: 'Halaman tidak ditemukan' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, posisiTersimpan) {
    if (posisiTersimpan) return posisiTersimpan
    if (to.path !== from.path) return { top: 0 }
    return false
  },
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.pastikanSiap()
  if (to.meta.perluMasuk && !auth.sudahMasuk) return { name: 'masuk', query: { next: to.fullPath } }
  if (to.meta.tamu && auth.sudahMasuk) return tujuanAman(to.query.next)
  return true
})

router.afterEach((to, from) => {
  document.title = to.meta.judul ? `${to.meta.judul} · Polibatam Press` : 'Polibatam Press'
  // Pindah halaman (bukan sekadar ganti filter): fokus ke konten utama agar pembaca layar mulai dari sana.
  if (from.matched.length && to.path !== from.path) {
    nextTick(() => document.getElementById('konten')?.focus({ preventScroll: true }))
  }
})

export default router
