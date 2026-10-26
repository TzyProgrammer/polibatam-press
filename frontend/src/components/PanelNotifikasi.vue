<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { Bell, BellOff } from '@lucide/vue'

import { useDaftarNotifikasi } from '../composables/daftarNotifikasi'
import { useNotifikasiStore } from '../stores/notifikasi'
import DaftarNotifikasi from './DaftarNotifikasi.vue'
import KotakPesan from './KotakPesan.vue'

// Tombol lonceng dengan panel notifikasi (pola disclosure): klik membuka/menutup, Escape dan klik di luar
// menutup, fokus kembali ke tombol. Daftar dimuat ulang setiap kali panel dibuka.
const toko = useNotifikasiStore()
const route = useRoute()
const { daftar, adaLagi, memuat, galat, muatAwal, muatLagi, baca, bacaSemua } = useDaftarNotifikasi()

const terbuka = ref(false)
const akar = ref(null)
const tombol = ref(null)
const panel = ref(null)

function batasi(n) {
  return n > 99 ? '99+' : String(n)
}

async function buka() {
  terbuka.value = true
  muatAwal()
  await nextTick()
  panel.value?.focus()
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

function klikLuar(event) {
  if (terbuka.value && akar.value && !akar.value.contains(event.target)) tutup(false)
}

onMounted(() => document.addEventListener('pointerdown', klikLuar))
onBeforeUnmount(() => document.removeEventListener('pointerdown', klikLuar))
watch(() => route.fullPath, () => tutup(false))
</script>

<template>
  <div ref="akar" class="notif">
    <button
      ref="tombol"
      type="button"
      class="tombol-ikon"
      :aria-expanded="terbuka ? 'true' : 'false'"
      aria-controls="panel-notifikasi"
      :aria-label="`Notifikasi, ${toko.belumDibaca} belum dibaca`"
      @click="alih"
    >
      <Bell :size="24" />
      <span v-if="toko.belumDibaca" class="lencana" aria-hidden="true">{{ batasi(toko.belumDibaca) }}</span>
    </button>

    <section
      v-if="terbuka"
      id="panel-notifikasi"
      ref="panel"
      class="notif__panel"
      tabindex="-1"
      aria-labelledby="judul-panel-notifikasi"
      @keydown.esc.stop="tutup()"
    >
      <div class="notif__kepala">
        <div class="notif__judul-wadah">
          <h2 id="judul-panel-notifikasi" class="notif__judul">Notifikasi</h2>
          <span class="notif__jumlah">
            {{ toko.belumDibaca ? `${toko.belumDibaca} belum dibaca` : 'Semua sudah dibaca' }}
          </span>
        </div>
        <button v-if="toko.belumDibaca" type="button" class="notif__tandai" @click="bacaSemua">Tandai semua dibaca</button>
      </div>

      <div class="notif__isi">
        <KotakPesan v-if="galat" jenis="galat" class="notif__galat">{{ galat }}</KotakPesan>
        <div v-if="!daftar && memuat" class="notif__kerangka" aria-busy="true" aria-label="Memuat notifikasi">
          <div v-for="n in 3" :key="n" class="kerangka" style="height: 64px" />
        </div>
        <div v-else-if="daftar && !daftar.length" class="notif__kosong">
          <BellOff :size="28" aria-hidden="true" />
          <p>Belum ada notifikasi.</p>
        </div>
        <DaftarNotifikasi v-else-if="daftar" :item="daftar" ringkas @pilih="baca" />
      </div>

      <div class="notif__kaki">
        <button v-if="adaLagi" type="button" class="notif__lagi" :disabled="memuat" @click="muatLagi">
          {{ memuat ? 'Memuat…' : 'Muat notifikasi lainnya' }}
        </button>
        <RouterLink :to="{ name: 'notifikasi' }" class="notif__semua">Lihat semua notifikasi</RouterLink>
      </div>
    </section>
  </div>
</template>

<style scoped>
.notif {
  position: relative;
}

.notif__panel {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  z-index: 30;
  display: flex;
  flex-direction: column;
  width: 400px;
  max-height: min(600px, calc(100dvh - 96px));
  overflow: hidden;
  border: 1px solid var(--garis);
  border-radius: var(--radius-besar);
  background: var(--permukaan);
  box-shadow: var(--bayangan);
}

.notif__panel:focus {
  outline: none;
}

.notif__panel:focus-visible {
  outline: 3px solid var(--navy);
  outline-offset: 2px;
}

.notif__kepala {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 4px 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--garis-lembut);
}

.notif__judul-wadah {
  display: flex;
  flex-direction: column;
}

.notif__judul {
  font-size: 1.0625rem;
}

.notif__jumlah {
  color: var(--teks-redup);
  font-size: 0.8125rem;
}

.notif__tandai,
.notif__lagi {
  min-height: 44px;
  padding: 0 10px;
  border: 0;
  border-radius: var(--radius-kecil);
  background: transparent;
  color: var(--navy);
  font-size: 0.875rem;
  font-weight: 700;
  cursor: pointer;
}

.notif__tandai:hover,
.notif__lagi:hover {
  background: var(--navy-50);
}

.notif__isi {
  flex: 1;
  overflow-y: auto;
  overscroll-behavior: contain;
}

.notif__galat {
  margin: 12px 16px;
}

.notif__kerangka {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 16px;
}

.notif__kosong {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 32px 16px;
  color: var(--teks-redup);
}

.notif__kaki {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 4px 12px;
  padding: 4px 8px;
  border-top: 1px solid var(--garis-lembut);
}

.notif__semua {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  margin-left: auto;
  padding: 0 10px;
  font-size: 0.875rem;
  font-weight: 700;
}

@media (max-width: 719px) {
  .notif__panel {
    position: fixed;
    top: 64px;
    right: 8px;
    left: 8px;
    width: auto;
    max-height: calc(100dvh - 80px);
  }
}
</style>
