<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { ChevronDown } from '@lucide/vue'

import { useAuthStore } from '../stores/auth'

// Tombol avatar dengan menu tarik-turun (pola menu button WAI-ARIA): panah atas/bawah berpindah item,
// Escape menutup dan mengembalikan fokus ke tombol, klik di luar menutup menu.
const emit = defineEmits(['keluar'])
const auth = useAuthStore()
const route = useRoute()

const terbuka = ref(false)
const akar = ref(null)
const tombol = ref(null)
const menu = ref(null)

function daftarItem() {
  return [...(menu.value?.querySelectorAll('[role="menuitem"]') || [])]
}

async function buka(keAkhir = false) {
  terbuka.value = true
  await nextTick()
  const item = daftarItem()
  ;(keAkhir ? item[item.length - 1] : item[0])?.focus()
}

function tutup(kembalikanFokus = true) {
  if (!terbuka.value) return
  terbuka.value = false
  if (kembalikanFokus) tombol.value?.focus()
}

function alih() {
  if (terbuka.value) tutup()
  else buka()
}

function tombolTekan(event) {
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    buka()
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    buka(true)
  }
}

function menuTekan(event) {
  const item = daftarItem()
  const posisi = item.indexOf(document.activeElement)
  const pindah = {
    ArrowDown: (posisi + 1) % item.length,
    ArrowUp: (posisi - 1 + item.length) % item.length,
    Home: 0,
    End: item.length - 1,
  }
  if (event.key in pindah) {
    event.preventDefault()
    item[pindah[event.key]]?.focus()
  } else if (event.key === 'Escape') {
    event.preventDefault()
    tutup()
  } else if (event.key === 'Tab') {
    tutup(false)
  }
}

function klikLuar(event) {
  if (terbuka.value && akar.value && !akar.value.contains(event.target)) tutup(false)
}

function keluar() {
  tutup(false)
  emit('keluar')
}

onMounted(() => document.addEventListener('pointerdown', klikLuar))
onBeforeUnmount(() => document.removeEventListener('pointerdown', klikLuar))
watch(() => route.fullPath, () => tutup(false))
</script>

<template>
  <div ref="akar" class="menu-akun">
    <button
      ref="tombol"
      type="button"
      class="menu-akun__tombol"
      aria-haspopup="menu"
      :aria-expanded="terbuka ? 'true' : 'false'"
      aria-controls="menu-akun"
      :aria-label="`Menu akun ${auth.pengguna?.nama_lengkap || ''}`"
      @click="alih"
      @keydown="tombolTekan"
    >
      <span class="menu-akun__avatar" aria-hidden="true">{{ auth.inisial }}</span>
      <ChevronDown :size="18" />
    </button>
    <div v-show="terbuka" class="menu-akun__panel">
      <div class="menu-akun__identitas">
        <span class="menu-akun__nama">{{ auth.pengguna?.nama_lengkap }}</span>
        <span class="menu-akun__email">{{ auth.pengguna?.email }}</span>
      </div>
      <div id="menu-akun" ref="menu" role="menu" aria-label="Menu akun" @keydown="menuTekan">
        <RouterLink role="menuitem" :to="{ name: 'profil' }" class="menu-akun__item">Profil</RouterLink>
        <RouterLink role="menuitem" :to="{ name: 'pesanan' }" class="menu-akun__item">Pesanan saya</RouterLink>
        <RouterLink role="menuitem" :to="{ name: 'koleksi' }" class="menu-akun__item">Koleksi</RouterLink>
        <RouterLink role="menuitem" :to="{ name: 'isbn' }" class="menu-akun__item">Pengajuan ISBN</RouterLink>
        <div role="separator" class="menu-akun__pemisah" />
        <button role="menuitem" type="button" class="menu-akun__item" @click="keluar">Keluar</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.menu-akun {
  position: relative;
}

.menu-akun__tombol {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 44px;
  padding: 0 6px;
  border: 0;
  border-radius: var(--radius-kecil);
  background: transparent;
  color: var(--teks);
  cursor: pointer;
}

.menu-akun__tombol:hover {
  background: var(--navy-50);
}

.menu-akun__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--navy);
  color: #fff;
  font-size: 0.75rem;
  font-weight: 700;
}

.menu-akun__panel {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  z-index: 20;
  width: 240px;
  padding: 8px;
  border: 1px solid var(--garis);
  border-radius: var(--radius-besar);
  background: var(--permukaan);
  box-shadow: var(--bayangan);
}

.menu-akun__identitas {
  display: flex;
  flex-direction: column;
  padding: 8px 10px 10px;
  border-bottom: 1px solid var(--garis-lembut);
  margin-bottom: 6px;
}

.menu-akun__nama {
  font-weight: 700;
  overflow-wrap: anywhere;
}

.menu-akun__email {
  font-size: 0.8125rem;
  color: var(--teks-redup);
  overflow-wrap: anywhere;
}

.menu-akun__item {
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 44px;
  padding: 0 10px;
  border: 0;
  border-radius: var(--radius-kecil);
  background: transparent;
  color: var(--teks);
  font-size: 0.9375rem;
  font-weight: 600;
  text-align: left;
  text-decoration: none;
  cursor: pointer;
}

.menu-akun__item:hover,
.menu-akun__item:focus-visible {
  background: var(--navy-50);
  color: var(--navy);
}

.menu-akun__pemisah {
  height: 1px;
  margin: 6px 0;
  background: var(--garis-lembut);
}
</style>
