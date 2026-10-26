<script setup>
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { BookOpen, FileText, LogOut, Menu, ReceiptText, Search, ShoppingCart, Store, User, X } from '@lucide/vue'

import logo from '../assets/logo-polibatam-press.jpg'
import { useAuthStore } from '../stores/auth'
import { useKeranjangStore } from '../stores/keranjang'
import { usePesanStore } from '../stores/pesan'
import MenuAkun from './MenuAkun.vue'
import PanelNotifikasi from './PanelNotifikasi.vue'

const auth = useAuthStore()
const keranjang = useKeranjangStore()
const pesan = usePesanStore()
const route = useRoute()
const router = useRouter()

const MENU = [
  { id: 'katalog', label: 'Katalog', to: { name: 'beranda' }, ikon: Store, publik: true },
  { id: 'koleksi', label: 'Koleksi', to: { name: 'koleksi' }, ikon: BookOpen },
  { id: 'pesanan', label: 'Pesanan', to: { name: 'pesanan' }, ikon: ReceiptText },
  { id: 'isbn', label: 'Pengajuan ISBN', to: { name: 'isbn' }, ikon: FileText, publik: true },
]
const menu = computed(() => MENU.filter((m) => auth.sudahMasuk || m.publik))
const menuAktif = computed(() => route.meta.menu)

// Setelah masuk atau daftar, pengguna kembali ke halaman tempat ia menekan tombol.
const kembaliKe = computed(() => (route.meta.tamu ? route.query : { next: route.fullPath }))

const kataKunci = ref('')
watch(
  () => route.query.q,
  (q) => {
    kataKunci.value = typeof q === 'string' ? q : ''
  },
  { immediate: true },
)

function cari() {
  const q = kataKunci.value.trim()
  router.push({ name: 'beranda', query: q ? { q } : {} })
  tutupLaci()
}

function batasi(n) {
  return n > 99 ? '99+' : String(n)
}

const laci = ref(null)

function bukaLaci() {
  laci.value?.showModal()
}

function tutupLaci() {
  if (laci.value?.open) laci.value.close()
}

function klikLaci(event) {
  if (event.target === laci.value) tutupLaci()
}

watch(() => route.fullPath, tutupLaci)

async function keluar() {
  tutupLaci()
  await auth.keluar()
  pesan.tampilkan('Anda sudah keluar.', { jenis: 'info' })
  router.push({ name: 'beranda' })
}
</script>

<template>
  <header class="kepala">
    <div class="wadah kepala__baris">
      <button type="button" class="tombol-ikon kepala__laci" aria-label="Buka menu" @click="bukaLaci">
        <Menu :size="24" />
      </button>

      <RouterLink :to="{ name: 'beranda' }" class="merek" aria-label="Polibatam Press, ke beranda">
        <img :src="logo" alt="" width="44" height="44" class="merek__logo">
        <span class="merek__nama">Polibatam Press</span>
      </RouterLink>

      <form class="cari" role="search" @submit.prevent="cari">
        <label class="cari__kotak">
          <Search :size="20" />
          <span class="sr-only">Cari buku</span>
          <input
            v-model="kataKunci"
            type="search"
            name="q"
            placeholder="Cari judul, penulis, atau ISBN"
            autocomplete="off"
            enterkeyhint="search"
          >
        </label>
      </form>

      <div class="kepala__aksi">
        <template v-if="auth.sudahMasuk">
          <RouterLink
            :to="{ name: 'keranjang' }"
            class="tombol-ikon"
            :aria-label="`Keranjang, ${keranjang.jumlahItem} item`"
          >
            <ShoppingCart :size="24" />
            <span v-if="keranjang.jumlahItem" class="lencana" aria-hidden="true">{{ batasi(keranjang.jumlahItem) }}</span>
          </RouterLink>
          <PanelNotifikasi />
          <MenuAkun class="kepala__akun" @keluar="keluar" />
        </template>
        <template v-else>
          <RouterLink :to="{ name: 'masuk', query: kembaliKe }" class="tombol tombol--sekunder kepala__tombol">Masuk</RouterLink>
          <RouterLink :to="{ name: 'daftar', query: kembaliKe }" class="tombol tombol--utama kepala__tombol kepala__daftar">
            Daftar
          </RouterLink>
        </template>
      </div>
    </div>

    <nav class="kepala__nav" aria-label="Navigasi utama">
      <div class="wadah kepala__nav-isi">
        <RouterLink
          v-for="m in menu"
          :key="m.id"
          :to="m.to"
          class="kepala__tautan"
          :class="{ 'is-aktif': menuAktif === m.id }"
          :aria-current="menuAktif === m.id ? 'page' : undefined"
        >
          {{ m.label }}
        </RouterLink>
      </div>
    </nav>

    <dialog ref="laci" class="laci" aria-labelledby="judul-laci" @click="klikLaci">
      <div class="laci__isi">
        <div class="laci__kepala">
          <h2 id="judul-laci" class="laci__judul">Menu</h2>
          <button type="button" class="tombol-ikon" aria-label="Tutup menu" @click="tutupLaci">
            <X :size="24" />
          </button>
        </div>
        <div v-if="auth.sudahMasuk" class="laci__identitas">
          <span class="laci__avatar" aria-hidden="true">{{ auth.inisial }}</span>
          <span class="laci__nama">{{ auth.pengguna.nama_lengkap }}</span>
        </div>
        <nav aria-label="Menu navigasi">
          <RouterLink
            v-for="m in menu"
            :key="m.id"
            :to="m.to"
            class="laci__tautan"
            :class="{ 'is-aktif': menuAktif === m.id }"
            :aria-current="menuAktif === m.id ? 'page' : undefined"
          >
            <component :is="m.ikon" :size="20" />
            {{ m.label }}
          </RouterLink>
        </nav>
        <div class="laci__pemisah" />
        <template v-if="auth.sudahMasuk">
          <RouterLink :to="{ name: 'profil' }" class="laci__tautan">
            <User :size="20" />
            Profil
          </RouterLink>
          <button type="button" class="laci__tautan laci__keluar" @click="keluar">
            <LogOut :size="20" />
            Keluar
          </button>
        </template>
        <div v-else class="laci__tamu">
          <RouterLink :to="{ name: 'masuk', query: kembaliKe }" class="tombol tombol--sekunder tombol--penuh">Masuk</RouterLink>
          <RouterLink :to="{ name: 'daftar', query: kembaliKe }" class="tombol tombol--utama tombol--penuh">Daftar</RouterLink>
        </div>
      </div>
    </dialog>
  </header>
</template>

<style scoped>
.kepala {
  border-bottom: 1px solid var(--garis);
  background: var(--permukaan);
}

.kepala__baris {
  display: grid;
  grid-template-areas: 'merek cari aksi';
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px 24px;
  padding-block: 12px;
}

.kepala__laci {
  display: none;
  grid-area: laci;
}

.merek {
  display: inline-flex;
  grid-area: merek;
  align-items: center;
  gap: 10px;
  color: var(--teks);
  text-decoration: none;
}

.merek:hover {
  color: var(--navy);
}

.merek__logo {
  width: 44px;
  height: 44px;
}

.merek__nama {
  font-family: var(--font-judul);
  font-size: 1.0625rem;
  font-weight: 700;
  white-space: nowrap;
}

.cari {
  grid-area: cari;
  width: 100%;
  max-width: 640px;
}

.cari__kotak {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 44px;
  padding: 0 14px;
  border: 1px solid var(--garis-isian);
  border-radius: var(--radius-kecil);
  background: var(--permukaan);
  color: var(--teks-redup);
}

.cari__kotak:focus-within {
  border-color: var(--navy);
  outline: 3px solid var(--navy);
  outline-offset: 1px;
}

.cari__kotak input {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--teks);
  font-size: 0.9375rem;
}

.kepala__aksi {
  display: flex;
  grid-area: aksi;
  align-items: center;
  justify-self: end;
  gap: 4px;
}

.kepala__tombol {
  min-height: 40px;
  padding: 0 16px;
}

.kepala__daftar {
  margin-left: 4px;
}

.kepala__nav {
  border-top: 1px solid var(--garis-lembut);
}

.kepala__nav-isi {
  display: flex;
  gap: 4px;
  overflow-x: auto;
  padding-inline: 16px;
}

.kepala__tautan {
  display: flex;
  flex: none;
  align-items: center;
  height: 44px;
  padding: 0 8px;
  border-bottom: 3px solid transparent;
  color: var(--teks-redup);
  font-size: 0.9375rem;
  font-weight: 600;
  text-decoration: none;
  white-space: nowrap;
}

.kepala__tautan:hover {
  color: var(--navy);
}

.kepala__tautan.is-aktif {
  border-bottom-color: var(--jingga);
  color: var(--navy);
}

/* Laci menu ponsel */
.laci {
  inset: 0 auto 0 0;
  width: min(320px, 86vw);
  max-width: none;
  height: 100dvh;
  max-height: none;
  margin: 0;
  padding: 0;
  border: 0;
  background: var(--permukaan);
  color: var(--teks);
}

.laci::backdrop {
  background: rgba(20, 38, 77, 0.45);
}

.laci__isi {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-height: 100%;
  padding: 8px 16px 24px;
}

.laci__kepala {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.laci__judul {
  font-size: 1.125rem;
}

.laci__identitas {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
  padding: 12px;
  border-radius: var(--radius);
  background: var(--navy-50);
}

.laci__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--navy);
  color: #fff;
  font-size: 0.875rem;
  font-weight: 700;
}

.laci__nama {
  font-weight: 600;
}

.laci__tautan {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  min-height: 48px;
  padding: 0 12px;
  border: 0;
  border-radius: var(--radius-kecil);
  background: transparent;
  color: var(--teks);
  font-size: 1rem;
  font-weight: 600;
  text-align: left;
  text-decoration: none;
  cursor: pointer;
}

.laci__tautan:hover,
.laci__tautan.is-aktif {
  background: var(--navy-50);
  color: var(--navy);
}

.laci__pemisah {
  height: 1px;
  margin: 8px 0;
  background: var(--garis-lembut);
}

.laci__tamu {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

@media (max-width: 719px) {
  .kepala__baris {
    grid-template-areas:
      'laci merek aksi'
      'cari cari cari';
    gap: 8px;
    padding-block: 8px 12px;
  }

  .kepala__laci {
    display: inline-flex;
  }

  .merek__logo {
    width: 36px;
    height: 36px;
  }

  .merek__nama {
    font-size: 0.9375rem;
  }

  .cari {
    max-width: none;
  }

  .kepala__nav,
  .kepala__akun,
  .kepala__daftar {
    display: none;
  }
}
</style>
