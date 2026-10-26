<script setup>
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { BellOff, CheckCheck } from '@lucide/vue'

import DaftarNotifikasi from '../components/DaftarNotifikasi.vue'
import KotakPesan from '../components/KotakPesan.vue'
import { useDaftarNotifikasi } from '../composables/daftarNotifikasi'
import { useNotifikasiStore } from '../stores/notifikasi'

// Semua notifikasi pengguna, terbaru lebih dulu. Filter "Belum dibaca" disimpan di URL (?status=baru).
const route = useRoute()
const router = useRouter()
const toko = useNotifikasiStore()

const hanyaBaru = computed(() => route.query.status === 'baru')
const { daftar, adaLagi, memuat, galat, muatAwal, muatLagi, baca, bacaSemua } = useDaftarNotifikasi(() => hanyaBaru.value)

watch(hanyaBaru, () => muatAwal(), { immediate: true })

function pilihFilter(baru) {
  router.replace({ name: 'notifikasi', query: baru ? { status: 'baru' } : {} })
}
</script>

<template>
  <div class="wadah halaman halaman-notif">
    <div class="halaman__kepala">
      <h1 class="halaman__judul">Notifikasi</h1>
      <p class="halaman__sub">Kabar tentang pesanan, koleksi digital, dan pengajuan ISBN Anda.</p>
    </div>

    <div class="alat">
      <div class="alat__saring" role="group" aria-label="Saring notifikasi">
        <button type="button" class="pil" :aria-pressed="hanyaBaru ? 'false' : 'true'" @click="pilihFilter(false)">Semua</button>
        <button type="button" class="pil" :aria-pressed="hanyaBaru ? 'true' : 'false'" @click="pilihFilter(true)">
          Belum dibaca ({{ toko.belumDibaca }})
        </button>
      </div>
      <button v-if="toko.belumDibaca" type="button" class="tombol tombol--sekunder" @click="bacaSemua">
        <CheckCheck :size="18" aria-hidden="true" />
        Tandai semua dibaca
      </button>
    </div>

    <KotakPesan v-if="galat" jenis="galat" class="halaman-notif__galat">
      <span>{{ galat }}</span>
      <button type="button" class="tombol tombol--sekunder" @click="muatAwal">Coba lagi</button>
    </KotakPesan>

    <div v-if="!daftar && memuat" class="kartu kartu--isi" aria-busy="true" aria-label="Memuat notifikasi">
      <div v-for="n in 4" :key="n" class="kerangka" style="height: 64px; margin-bottom: 12px" />
    </div>

    <div v-else-if="daftar && !daftar.length" class="kartu kartu--isi kosong">
      <BellOff :size="40" class="kosong__ikon" aria-hidden="true" />
      <h2 class="kosong__judul">{{ hanyaBaru ? 'Tidak ada notifikasi yang belum dibaca' : 'Belum ada notifikasi' }}</h2>
      <p class="kosong__teks">Notifikasi muncul saat status pesanan, akses konten, atau pengajuan ISBN Anda berubah.</p>
    </div>

    <template v-else-if="daftar">
      <div class="kartu daftar-wadah">
        <DaftarNotifikasi :item="daftar" @pilih="baca" />
      </div>
      <div v-if="adaLagi" class="lagi">
        <button type="button" class="tombol tombol--sekunder" :disabled="memuat" @click="muatLagi">
          {{ memuat ? 'Memuat…' : 'Muat notifikasi lainnya' }}
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.halaman-notif {
  max-width: 880px;
}

.alat {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.alat__saring {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.halaman-notif__galat {
  margin-bottom: 16px;
}

.daftar-wadah {
  overflow: hidden;
}

.lagi {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}

.kosong {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding-block: 48px;
  text-align: center;
}

.kosong__ikon {
  color: var(--navy);
}

.kosong__judul {
  font-size: 1.25rem;
}

.kosong__teks {
  max-width: 480px;
  color: var(--teks-redup);
}
</style>
