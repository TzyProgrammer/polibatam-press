import { nextTick } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '../stores/auth'
import { tujuanAman } from '../utils/navigasi'
import BerandaView from '../views/BerandaView.vue'

const Segera = () => import('../views/SegeraView.vue')

// meta.perluMasuk: hanya untuk pengguna yang sudah masuk. meta.tamu: hanya untuk yang belum masuk.
// meta.menu: menu header yang ditandai aktif. meta.tahap: halaman yang dibuat di tahap berikutnya.
const routes = [
  { path: '/', name: 'beranda', component: BerandaView, meta: { judul: 'Katalog', menu: 'katalog' } },
  {
    path: '/buku/:slug',
    name: 'buku',
    component: () => import('../views/DetailBukuView.vue'),
    meta: { judul: 'Detail buku', menu: 'katalog' },
  },
  { path: '/masuk', name: 'masuk', component: () => import('../views/MasukView.vue'), meta: { judul: 'Masuk', tamu: true } },
  {
    path: '/daftar',
    name: 'daftar',
    component: () => import('../views/DaftarView.vue'),
    meta: { judul: 'Daftar akun', tamu: true },
  },
  {
    path: '/profil',
    name: 'profil',
    component: () => import('../views/ProfilView.vue'),
    meta: { judul: 'Profil', perluMasuk: true },
  },
  { path: '/keranjang', name: 'keranjang', component: Segera, meta: { judul: 'Keranjang', perluMasuk: true, tahap: 'H2' } },
  { path: '/checkout', name: 'checkout', component: Segera, meta: { judul: 'Checkout', perluMasuk: true, tahap: 'H2' } },
  {
    path: '/pesanan',
    name: 'pesanan',
    component: Segera,
    meta: { judul: 'Pesanan saya', perluMasuk: true, menu: 'pesanan', tahap: 'H2' },
  },
  {
    path: '/pesanan/:nomor',
    name: 'pesanan-detail',
    component: Segera,
    meta: { judul: 'Detail pesanan', perluMasuk: true, menu: 'pesanan', tahap: 'H2' },
  },
  {
    path: '/koleksi',
    name: 'koleksi',
    component: Segera,
    meta: { judul: 'Koleksi saya', perluMasuk: true, menu: 'koleksi', tahap: 'H3' },
  },
  {
    path: '/isbn',
    name: 'isbn',
    component: Segera,
    meta: { judul: 'Pengajuan ISBN', perluMasuk: true, menu: 'isbn', tahap: 'H4' },
  },
  {
    path: '/isbn/:id',
    name: 'isbn-detail',
    component: Segera,
    meta: { judul: 'Pengajuan ISBN', perluMasuk: true, menu: 'isbn', tahap: 'H4' },
  },
  { path: '/notifikasi', name: 'notifikasi', component: Segera, meta: { judul: 'Notifikasi', perluMasuk: true, tahap: 'H4' } },
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
