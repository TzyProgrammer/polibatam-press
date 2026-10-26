<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { BookOpen, Headphones, Library, Lock, ShieldCheck } from '@lucide/vue'

import { api } from '../api/klien'
import KotakPesan from '../components/KotakPesan.vue'
import SampulBuku from '../components/SampulBuku.vue'
import { formatDurasi, formatTanggal } from '../utils/format'

// GET /api/koleksi/: ebook dan audiobook milik pembeli beserta status kontennya (FR-13).
// Filter jenis disimpan di URL (?tipe=ebook|audiobook).
const TIPE = [
  { nilai: '', label: 'Semua' },
  { nilai: 'ebook', label: 'Ebook' },
  { nilai: 'audiobook', label: 'Audiobook' },
]
const JEDA_PANTAU_MS = 10000
const BATAS_PANTAU = 12 // berhenti setelah ±2 menit; muat ulang halaman untuk memeriksa lagi

const route = useRoute()
const router = useRouter()

const daftar = ref(null)
const galat = ref('')
let pewaktu = null
let putaranPantau = 0

const tipe = computed(() => (['ebook', 'audiobook'].includes(route.query.tipe) ? route.query.tipe : ''))
const tampil = computed(() => (daftar.value || []).filter((k) => !tipe.value || k.format === tipe.value))

// Konten yang sedang disiapkan server (salinan ebook, paket audiobook) dipantau berkala agar statusnya
// berubah tanpa memuat ulang halaman.
const adaYangDisiapkan = computed(() =>
  (daftar.value || []).some((k) => k.aktif && ['menunggu', 'diproses'].includes(k.status)),
)

async function muat({ diam = false } = {}) {
  if (!diam) galat.value = ''
  try {
    daftar.value = await api.get('/koleksi/')
  } catch (e) {
    if (!diam && e.status !== 401) galat.value = e.detail
  }
}

muat()

watch(adaYangDisiapkan, (ada) => {
  clearInterval(pewaktu)
  pewaktu = null
  if (!ada) return
  putaranPantau = 0
  pewaktu = setInterval(() => {
    if (++putaranPantau > BATAS_PANTAU) {
      clearInterval(pewaktu)
      return
    }
    if (document.visibilityState === 'visible') muat({ diam: true })
  }, JEDA_PANTAU_MS)
})

onBeforeUnmount(() => clearInterval(pewaktu))

function pilihTipe(nilai) {
  router.replace({ name: 'koleksi', query: nilai ? { tipe: nilai } : {} })
}

function bisaDibuka(k) {
  if (!k.aktif || ['dicabut', 'gagal'].includes(k.status)) return false
  // Salinan ebook disiapkan saat dibuka; audiobook harus sudah dikemas.
  return k.format === 'ebook' || k.status === 'siap'
}

function labelStatus(k) {
  if (!k.aktif || k.status === 'dicabut') return 'Akses dinonaktifkan admin'
  if (k.status === 'siap') return k.format === 'ebook' ? 'Siap dibaca' : 'Siap diputar'
  if (k.status === 'gagal') return 'Gagal disiapkan'
  if (k.format === 'audiobook') return 'Audiobook sedang disiapkan'
  return k.status === 'diproses' ? 'Sedang diproses' : 'Menunggu diproses'
}

function catatan(k) {
  if (!k.aktif || k.status === 'dicabut') return 'Hubungi Polibatam Press bila ada pertanyaan.'
  if (k.status === 'gagal') return 'Konten gagal disiapkan. Hubungi admin Polibatam Press.'
  if (k.format === 'ebook' && k.status !== 'siap') return 'Ebook tetap bisa dibuka; salinan ber-watermark disiapkan otomatis.'
  if (k.format === 'audiobook' && k.status !== 'siap') return 'Coba lagi beberapa saat lagi.'
  return ''
}

function gayaStatus(k) {
  if (!k.aktif || k.status === 'dicabut') return 'tutup'
  if (k.status === 'siap') return 'siap'
  return k.status === 'gagal' ? 'gagal' : 'tunggu'
}

function rincian(k) {
  if (k.format === 'audiobook' && k.durasi_detik) return `${k.format_label} · ${formatDurasi(k.durasi_detik)}`
  if (k.format === 'ebook' && k.buku.jumlah_halaman) return `${k.format_label} · ${k.buku.jumlah_halaman} halaman`
  return k.format_label
}

function tujuan(k) {
  return k.format === 'ebook'
    ? { name: 'baca-ebook', params: { produkId: k.produk_id } }
    : { name: 'putar-audiobook', params: { produkId: k.produk_id } }
}
</script>

<template>
  <div class="wadah halaman">
    <div class="halaman__kepala">
      <h1 class="halaman__judul">Koleksi saya</h1>
      <p class="halaman__sub">Ebook dan audiobook yang sudah Anda beli.</p>
    </div>

    <div class="pengingat">
      <ShieldCheck :size="22" class="pengingat__ikon" aria-hidden="true" />
      <p>
        Ebook diberi watermark berisi nama Anda, email yang disamarkan, dan kode unik. Audiobook diputar lewat streaming
        terenkripsi dan tidak bisa diunduh. Jangan bagikan konten kepada orang lain.
      </p>
    </div>

    <div class="saring" role="group" aria-label="Saring koleksi">
      <button
        v-for="t in TIPE"
        :key="t.nilai"
        type="button"
        class="pil"
        :aria-pressed="tipe === t.nilai ? 'true' : 'false'"
        @click="pilihTipe(t.nilai)"
      >
        {{ t.label }}
      </button>
    </div>

    <KotakPesan v-if="galat && !daftar" jenis="galat">
      <span>{{ galat }}</span>
      <button type="button" class="tombol tombol--sekunder" @click="muat()">Coba lagi</button>
    </KotakPesan>

    <div v-else-if="!daftar" class="grid-koleksi" aria-busy="true" aria-label="Memuat koleksi">
      <div v-for="n in 4" :key="n" class="kerangka" style="height: 168px" />
    </div>

    <div v-else-if="!tampil.length" class="kartu kartu--isi kosong">
      <Library :size="40" class="kosong__ikon" aria-hidden="true" />
      <h2 class="kosong__judul">{{ tipe ? `Belum ada ${tipe} di koleksi` : 'Koleksi masih kosong' }}</h2>
      <p class="kosong__teks">Ebook dan audiobook masuk ke sini setelah pembayaran lunas.</p>
      <RouterLink :to="{ name: 'beranda', query: tipe ? { tipe } : {} }" class="tombol tombol--utama">
        Lihat katalog
      </RouterLink>
    </div>

    <ul v-else class="grid-koleksi">
      <li v-for="k in tampil" :key="k.produk_id" class="kartu item-koleksi" :class="{ 'is-nonaktif': !bisaDibuka(k) }">
        <SampulBuku class="item-koleksi__sampul" :src="k.buku.sampul || ''" />
        <div class="item-koleksi__isi">
          <h2 class="item-koleksi__judul">{{ k.buku.judul }}</h2>
          <p class="item-koleksi__penulis">{{ k.buku.penulis }}</p>
          <p class="item-koleksi__rincian">{{ rincian(k) }}</p>
          <p class="item-koleksi__pesanan">
            <RouterLink :to="{ name: 'pesanan-detail', params: { nomor: k.nomor_pesanan } }">{{ k.nomor_pesanan }}</RouterLink>
            · {{ formatTanggal(k.diperoleh) }}
          </p>
          <span class="status-konten" :class="`status-konten--${gayaStatus(k)}`">
            <Lock v-if="gayaStatus(k) === 'tutup'" :size="14" aria-hidden="true" />
            {{ labelStatus(k) }}
          </span>
          <p v-if="catatan(k)" class="item-koleksi__catatan">{{ catatan(k) }}</p>
          <div class="item-koleksi__aksi">
            <RouterLink v-if="bisaDibuka(k)" :to="tujuan(k)" class="tombol tombol--utama">
              <component :is="k.format === 'ebook' ? BookOpen : Headphones" :size="18" aria-hidden="true" />
              {{ k.format === 'ebook' ? 'Baca' : 'Putar' }}
              <span class="sr-only">{{ k.buku.judul }}</span>
            </RouterLink>
            <button v-else type="button" class="tombol" disabled>
              <component :is="k.format === 'ebook' ? BookOpen : Headphones" :size="18" aria-hidden="true" />
              {{ k.format === 'ebook' ? 'Baca' : 'Putar' }}
              <span class="sr-only">{{ k.buku.judul }} (belum bisa dibuka)</span>
            </button>
          </div>
        </div>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.pengingat {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 20px;
  padding: 14px 16px;
  border: 1px solid var(--navy-100);
  border-radius: var(--radius);
  background: var(--navy-50);
  font-size: 0.9375rem;
}

.pengingat__ikon {
  flex: none;
  margin-top: 1px;
  color: var(--navy);
}

.saring {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 20px;
}

.grid-koleksi {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 360px), 1fr));
  gap: 16px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.item-koleksi {
  display: flex;
  gap: 16px;
  padding: 16px;
}

.item-koleksi__sampul {
  flex: none;
  align-self: flex-start;
  width: 96px;
  overflow: hidden;
  border: 1px solid var(--garis-lembut);
  border-radius: 6px;
}

.is-nonaktif .item-koleksi__sampul {
  opacity: 0.6;
}

.item-koleksi__isi {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  min-width: 0;
}

.item-koleksi__judul {
  font-family: var(--font-isi);
  font-size: 1.0625rem;
  font-weight: 700;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.item-koleksi__penulis,
.item-koleksi__rincian,
.item-koleksi__pesanan {
  color: var(--teks-redup);
  font-size: 0.875rem;
}

.item-koleksi__pesanan a {
  font-weight: 600;
}

.status-konten {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 6px;
  padding: 2px 10px;
  border: 1px solid var(--garis);
  border-radius: 999px;
  background: #eef1f5;
  color: var(--teks-redup);
  font-size: 0.8125rem;
  font-weight: 600;
}

.status-konten--siap {
  border-color: #abefc6;
  background: var(--sukses-50);
  color: var(--sukses);
}

.status-konten--tunggu {
  border-style: dashed;
  border-color: var(--jingga);
  background: var(--jingga-50);
  color: var(--teks);
}

.status-konten--gagal {
  border-color: #f4c7c3;
  background: var(--galat-50);
  color: var(--galat);
}

.item-koleksi__catatan {
  color: var(--teks-redup);
  font-size: 0.8125rem;
}

.item-koleksi__aksi {
  margin-top: auto;
  padding-top: 10px;
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
  margin-bottom: 8px;
  color: var(--teks-redup);
}

@media (max-width: 719px) {
  .item-koleksi {
    gap: 12px;
    padding: 12px;
  }

  .item-koleksi__sampul {
    width: 72px;
  }
}
</style>
