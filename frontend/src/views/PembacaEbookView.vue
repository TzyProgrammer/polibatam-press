<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { ArrowLeft, ChevronLeft, ChevronRight, LoaderCircle, Maximize, Minimize, Minus, Plus, ShieldCheck } from '@lucide/vue'

import { api } from '../api/klien'
import KotakPesan from '../components/KotakPesan.vue'
import { useAuthStore } from '../stores/auth'
import { muatPdfjs, opsiDokumen } from '../utils/pdf'
import { bacaPosisi, simpanPosisi } from '../utils/posisi'

// Pembaca ebook: salinan ber-watermark milik pembeli diminta lewat GET /api/drm/ebook/<produk_id>/
// (presigned URL 5 menit), diunduh sekali oleh PDF.js, lalu dirender per halaman ke canvas.
// Tidak ada tombol unduh: salinan ini memuat identitas pembeli sebagai watermark.
const TINGKAT_ZOOM = [0.5, 0.75, 1, 1.25, 1.5, 2, 3]
const JEDA_SIAP_MS = 3000
const BATAS_MENUNGGU = 40 // ±2 menit menunggu salinan disiapkan worker
const PIKSEL_MAKS = 16_000_000 // batas ukuran canvas (lebar × tinggi piksel) agar memori tetap aman

const route = useRoute()
const auth = useAuthStore()

const produkId = Number.parseInt(route.params.produkId, 10)
const info = ref(null)
const tahap = ref('memuat') // memuat | menyiapkan | mengunduh | siap | galat
const galat = ref('')
const kemajuan = ref(0)
const halaman = ref(1)
const jumlahHalaman = ref(0)
const skala = ref(1)
const pas = ref(true) // ukuran mengikuti layar sampai pembaca memperbesar atau memperkecil
const isianHalaman = ref('1')
const layarPenuh = ref(false)
const bisaLayarPenuh = typeof document !== 'undefined' && Boolean(document.fullscreenEnabled)

const akar = ref(null)
const area = ref(null)
const kanvas = ref(null)

let aktif = true
let generasi = 0 // naik setiap kali ebook dimuat (ulang), agar proses muat yang lama berhenti diam-diam
let dokumen = null
let tugasMuat = null
let tugasRender = null
let nomorRender = 0
let pewaktuUbahUkuran = null

const judul = computed(() => info.value?.buku.judul || 'Ebook')
const persen = computed(() => `${Math.round(skala.value * 100)}%`)

function tunggu(ms) {
  return new Promise((selesai) => setTimeout(selesai, ms))
}

async function ambilUrl(gen) {
  for (let percobaan = 0; percobaan < BATAS_MENUNGGU; percobaan++) {
    try {
      return (await api.get(`/drm/ebook/${produkId}/`)).url
    } catch (e) {
      // 409: salinan ber-watermark masih disiapkan worker (atau baru diantrikan oleh permintaan ini).
      if (e.status !== 409 || e.data?.status === 'gagal') throw e
      if (!aktif || gen !== generasi) return null
      tahap.value = 'menyiapkan'
      await tunggu(JEDA_SIAP_MS)
      if (!aktif || gen !== generasi) return null
    }
  }
  const galatLama = new Error('Salinan ebook masih disiapkan. Coba buka lagi beberapa saat lagi.')
  galatLama.detail = galatLama.message
  throw galatLama
}

async function mulai() {
  const gen = ++generasi
  tahap.value = 'memuat'
  galat.value = ''
  kemajuan.value = 0
  // Muat ulang (tombol "Coba lagi"): dokumen dan worker PDF.js sebelumnya dilepas dulu.
  tugasRender?.cancel()
  tugasMuat?.destroy()
  tugasMuat = null
  dokumen = null
  try {
    api
      .get('/koleksi/')
      .then((data) => {
        info.value = data.find((k) => k.produk_id === produkId && k.format === 'ebook') || null
        if (info.value) document.title = `${info.value.buku.judul} · Polibatam Press`
      })
      .catch(() => {})
    const [url, pdfjs] = await Promise.all([ambilUrl(gen), muatPdfjs()])
    if (!aktif || gen !== generasi || !url) return
    tahap.value = 'mengunduh'
    tugasMuat = pdfjs.getDocument(opsiDokumen(url))
    tugasMuat.onProgress = ({ loaded, total }) => {
      if (total) kemajuan.value = Math.min(1, loaded / total)
    }
    dokumen = await tugasMuat.promise
    if (!aktif || gen !== generasi) return
    jumlahHalaman.value = dokumen.numPages
    const tersimpan = Math.round(bacaPosisi('ebook', produkId, auth.pengguna?.id))
    halaman.value = Math.min(Math.max(1, tersimpan || 1), dokumen.numPages)
    isianHalaman.value = String(halaman.value)
    tahap.value = 'siap'
    await nextTick()
    await render()
  } catch (e) {
    if (!aktif || gen !== generasi || e?.status === 401) return
    tahap.value = 'galat'
    if (e?.status === 403) galat.value = e.detail
    else if (e?.status === 404) galat.value = 'Ebook tidak ditemukan.'
    else if (e?.detail) galat.value = e.detail
    else galat.value = 'Ebook tidak dapat dimuat. Periksa koneksi Anda lalu coba lagi.'
  }
}

// Render dari tombol, papan ketik, geseran, atau perubahan ukuran layar: bila halaman gagal digambar,
// tampilkan pesan dan tombol "Coba lagi" (posisi terakhir yang berhasil tetap tersimpan).
function tampilkan() {
  render().catch(() => {
    if (!aktif || tahap.value !== 'siap') return
    tahap.value = 'galat'
    galat.value = 'Halaman ini tidak dapat ditampilkan. Coba muat ulang ebook.'
  })
}

// Ukuran awal: satu halaman utuh terlihat (lebar dan tinggi area baca), dibatasi 50–200%.
function skalaPas(halamanPdf) {
  const dasar = halamanPdf.getViewport({ scale: 1 })
  const lebar = Math.max(200, (area.value?.clientWidth || window.innerWidth) - 32)
  const tinggi = Math.max(300, (area.value?.clientHeight || window.innerHeight) - 32)
  const nilai = Math.min(lebar / dasar.width, tinggi / dasar.height)
  return Math.min(2, Math.max(0.5, nilai))
}

async function render() {
  if (!dokumen || !kanvas.value) return
  const nomor = ++nomorRender
  const halamanPdf = await dokumen.getPage(halaman.value)
  if (!aktif || nomor !== nomorRender) return
  if (pas.value) skala.value = skalaPas(halamanPdf)
  const viewport = halamanPdf.getViewport({ scale: skala.value })
  const luas = viewport.width * viewport.height
  const rasio = Math.min(window.devicePixelRatio || 1, Math.sqrt(PIKSEL_MAKS / luas))
  const c = kanvas.value
  tugasRender?.cancel()
  c.width = Math.floor(viewport.width * rasio)
  c.height = Math.floor(viewport.height * rasio)
  c.style.width = `${Math.floor(viewport.width)}px`
  c.style.height = `${Math.floor(viewport.height)}px`
  tugasRender = halamanPdf.render({
    canvas: c,
    viewport,
    transform: rasio !== 1 ? [rasio, 0, 0, rasio, 0, 0] : undefined,
  })
  try {
    await tugasRender.promise
  } catch (e) {
    if (e?.name === 'RenderingCancelledException') return
    throw e
  }
  simpanPosisi('ebook', produkId, auth.pengguna?.id, halaman.value)
}

function keHalaman(nomor) {
  if (!dokumen) return
  const tujuan = Math.min(Math.max(1, Math.round(nomor) || 1), jumlahHalaman.value)
  isianHalaman.value = String(tujuan)
  if (tujuan === halaman.value) return
  halaman.value = tujuan
  if (area.value) area.value.scrollTop = 0
  tampilkan()
}

function terapkanIsian() {
  keHalaman(Number.parseInt(isianHalaman.value, 10))
}

function ubahZoom(arah) {
  const sekarang = skala.value
  const daftar = arah > 0 ? TINGKAT_ZOOM.filter((z) => z > sekarang + 0.01) : TINGKAT_ZOOM.filter((z) => z < sekarang - 0.01)
  const baru = arah > 0 ? daftar[0] : daftar[daftar.length - 1]
  if (!baru) return
  pas.value = false
  skala.value = baru
  tampilkan()
}

function sesuaikanLayar() {
  pas.value = true
  tampilkan()
}

async function alihLayarPenuh() {
  try {
    if (document.fullscreenElement) await document.exitFullscreen()
    else await akar.value?.requestFullscreen()
  } catch {
    // Peramban menolak (misalnya tidak dipicu langsung oleh pengguna): abaikan.
  }
}

function saatLayarPenuh() {
  layarPenuh.value = document.fullscreenElement === akar.value
  if (pas.value) setTimeout(tampilkan, 50)
}

function saatUbahUkuran() {
  if (!pas.value) return
  clearTimeout(pewaktuUbahUkuran)
  pewaktuUbahUkuran = setTimeout(tampilkan, 150)
}

// Pintasan papan ketik: panah kiri/kanan, Page Up/Down, Home/End (kecuali saat mengetik di isian).
function saatTombol(event) {
  if (tahap.value !== 'siap' || event.altKey || event.ctrlKey || event.metaKey) return
  if (event.target.closest?.('input, select, textarea')) return
  const aksi = {
    ArrowLeft: () => keHalaman(halaman.value - 1),
    PageUp: () => keHalaman(halaman.value - 1),
    ArrowRight: () => keHalaman(halaman.value + 1),
    PageDown: () => keHalaman(halaman.value + 1),
    Home: () => keHalaman(1),
    End: () => keHalaman(jumlahHalaman.value),
  }[event.key]
  if (aksi) {
    event.preventDefault()
    aksi()
  }
}

// Geser satu jari di layar sentuh untuk berpindah halaman, kecuali saat halaman diperbesar melebihi lebar
// layar (geseran dipakai untuk menggulir) atau saat mencubit dengan dua jari.
let awalSentuh = null
let jariAktif = 0

function sentuhMulai(event) {
  if (event.pointerType !== 'touch') return
  jariAktif += 1
  awalSentuh = jariAktif === 1 ? { x: event.clientX, y: event.clientY, jamak: false } : { ...awalSentuh, jamak: true }
}

function sentuhSelesai(event) {
  if (event.pointerType !== 'touch') return
  jariAktif = Math.max(0, jariAktif - 1)
  if (!awalSentuh || jariAktif > 0) return
  const { x, y, jamak } = awalSentuh
  awalSentuh = null
  const dx = event.clientX - x
  const dy = event.clientY - y
  const bisaDigeser = area.value && area.value.scrollWidth > area.value.clientWidth + 2
  if (jamak || bisaDigeser || Math.abs(dx) < 60 || Math.abs(dx) < Math.abs(dy) * 1.5) return
  keHalaman(halaman.value + (dx < 0 ? 1 : -1))
}

function sentuhBatal(event) {
  if (event.pointerType !== 'touch') return
  jariAktif = Math.max(0, jariAktif - 1)
  awalSentuh = null
}

onMounted(() => {
  document.addEventListener('keydown', saatTombol)
  document.addEventListener('fullscreenchange', saatLayarPenuh)
  window.addEventListener('resize', saatUbahUkuran)
  mulai()
})

onBeforeUnmount(() => {
  aktif = false
  document.removeEventListener('keydown', saatTombol)
  document.removeEventListener('fullscreenchange', saatLayarPenuh)
  window.removeEventListener('resize', saatUbahUkuran)
  clearTimeout(pewaktuUbahUkuran)
  tugasRender?.cancel()
  tugasMuat?.destroy()
  dokumen = null
})
</script>

<template>
  <div ref="akar" class="pembaca" :class="{ 'is-layar-penuh': layarPenuh }">
    <header class="bilah">
      <div class="bilah__kiri">
        <RouterLink :to="{ name: 'koleksi' }" class="bilah__kembali">
          <ArrowLeft :size="20" aria-hidden="true" />
          <span>Koleksi</span>
        </RouterLink>
        <div class="bilah__judul">
          <h1 class="bilah__nama">{{ judul }}</h1>
          <span class="bilah__format">Ebook (PDF)</span>
        </div>
      </div>

      <template v-if="tahap === 'siap'">
        <nav class="bilah__halaman" aria-label="Navigasi halaman">
          <button
            type="button"
            class="tombol-ikon"
            aria-label="Halaman sebelumnya"
            :aria-disabled="halaman <= 1 ? 'true' : undefined"
            @click="keHalaman(halaman - 1)"
          >
            <ChevronLeft :size="22" />
          </button>
          <label class="bilah__isian">
            <span class="sr-only">Nomor halaman</span>
            <input
              v-model="isianHalaman"
              type="number"
              inputmode="numeric"
              min="1"
              :max="jumlahHalaman"
              @change="terapkanIsian"
              @keydown.enter="terapkanIsian"
            >
          </label>
          <span class="bilah__dari">dari {{ jumlahHalaman }}</span>
          <button
            type="button"
            class="tombol-ikon"
            aria-label="Halaman berikutnya"
            :aria-disabled="halaman >= jumlahHalaman ? 'true' : undefined"
            @click="keHalaman(halaman + 1)"
          >
            <ChevronRight :size="22" />
          </button>
        </nav>

        <div class="bilah__tampilan" role="group" aria-label="Ukuran tampilan">
          <button type="button" class="tombol-ikon" aria-label="Perkecil" @click="ubahZoom(-1)">
            <Minus :size="20" />
          </button>
          <button
            type="button"
            class="bilah__persen"
            :aria-pressed="pas ? 'true' : 'false'"
            :aria-label="`Ukuran ${persen}. Tekan untuk menyesuaikan halaman dengan layar`"
            @click="sesuaikanLayar"
          >
            {{ persen }}
          </button>
          <button type="button" class="tombol-ikon" aria-label="Perbesar" @click="ubahZoom(1)">
            <Plus :size="20" />
          </button>
          <button
            v-if="bisaLayarPenuh"
            type="button"
            class="tombol-ikon bilah__layar-penuh"
            :aria-label="layarPenuh ? 'Keluar dari layar penuh' : 'Layar penuh'"
            :aria-pressed="layarPenuh ? 'true' : 'false'"
            @click="alihLayarPenuh"
          >
            <component :is="layarPenuh ? Minimize : Maximize" :size="20" />
          </button>
        </div>
      </template>
    </header>

    <p class="catatan-watermark">
      <ShieldCheck :size="18" aria-hidden="true" />
      <span class="catatan-watermark__panjang">
        Salinan ini diberi watermark nama Anda, email yang disamarkan, nomor pesanan, dan kode unik. Jangan bagikan
        isinya kepada orang lain.
      </span>
      <span class="catatan-watermark__pendek">Salinan ber-watermark atas nama Anda. Jangan dibagikan.</span>
    </p>

    <div
      ref="area"
      class="area"
      :class="{ 'area--geser': pas }"
      role="region"
      aria-label="Halaman ebook"
      @pointerdown="sentuhMulai"
      @pointerup="sentuhSelesai"
      @pointercancel="sentuhBatal"
    >
      <div v-if="tahap === 'galat'" class="keadaan">
        <KotakPesan jenis="galat">
          <span>{{ galat }}</span>
        </KotakPesan>
        <div class="keadaan__aksi">
          <button type="button" class="tombol tombol--utama" @click="mulai">Coba lagi</button>
          <RouterLink :to="{ name: 'koleksi' }" class="tombol tombol--sekunder">Kembali ke Koleksi</RouterLink>
        </div>
      </div>

      <div v-else-if="tahap !== 'siap'" class="keadaan" role="status">
        <LoaderCircle :size="32" class="keadaan__putar" aria-hidden="true" />
        <p v-if="tahap === 'menyiapkan'" class="keadaan__teks">
          Menyiapkan salinan ber-watermark untuk Anda. Biasanya kurang dari satu menit.
        </p>
        <template v-else-if="tahap === 'mengunduh'">
          <p class="keadaan__teks">Mengunduh ebook… {{ Math.round(kemajuan * 100) }}%</p>
          <div
            class="kemajuan"
            role="progressbar"
            aria-label="Kemajuan unduhan ebook"
            aria-valuemin="0"
            aria-valuemax="100"
            :aria-valuenow="Math.round(kemajuan * 100)"
          >
            <span :style="{ width: `${Math.round(kemajuan * 100)}%` }" />
          </div>
        </template>
        <p v-else class="keadaan__teks">Memuat ebook…</p>
      </div>

      <canvas
        v-show="tahap === 'siap'"
        ref="kanvas"
        class="halaman-pdf"
        role="img"
        :aria-label="`Halaman ${halaman} dari ${jumlahHalaman}, ${judul}`"
      />
    </div>

    <p class="sr-only" aria-live="polite">{{ tahap === 'siap' ? `Halaman ${halaman} dari ${jumlahHalaman}` : '' }}</p>
  </div>
</template>

<style scoped>
.pembaca {
  display: flex;
  flex-direction: column;
  height: 100dvh;
  background: #dfe3ea;
}

.bilah {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 16px;
  padding: 8px 16px;
  border-bottom: 1px solid var(--garis);
  background: var(--permukaan);
}

.bilah__kiri {
  display: flex;
  flex: 1 1 280px;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.bilah__kembali {
  display: inline-flex;
  flex: none;
  align-items: center;
  gap: 6px;
  min-height: 44px;
  padding: 0 10px 0 4px;
  border-radius: var(--radius-kecil);
  color: var(--navy);
  font-weight: 600;
  text-decoration: none;
}

.bilah__kembali:hover {
  background: var(--navy-50);
}

.bilah__judul {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.bilah__nama {
  overflow: hidden;
  font-family: var(--font-isi);
  font-size: 1rem;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bilah__format {
  color: var(--teks-redup);
  font-size: 0.8125rem;
}

.bilah__halaman,
.bilah__tampilan {
  display: flex;
  align-items: center;
  gap: 4px;
}

.bilah__halaman .tombol-ikon[aria-disabled='true'] {
  color: var(--garis-isian);
  cursor: not-allowed;
}

.bilah__halaman .tombol-ikon[aria-disabled='true']:hover {
  background: transparent;
}

.bilah__isian input {
  width: 64px;
  height: 40px;
  padding: 0 6px;
  border: 1px solid var(--garis-isian);
  border-radius: var(--radius-kecil);
  text-align: center;
  -moz-appearance: textfield;
}

.bilah__isian input::-webkit-inner-spin-button,
.bilah__isian input::-webkit-outer-spin-button {
  margin: 0;
  -webkit-appearance: none;
}

.bilah__dari {
  color: var(--teks-redup);
  font-size: 0.9375rem;
  white-space: nowrap;
}

.bilah__persen {
  min-width: 64px;
  min-height: 44px;
  border: 0;
  border-radius: var(--radius-kecil);
  background: transparent;
  color: var(--teks);
  font-weight: 600;
  cursor: pointer;
}

.bilah__persen:hover,
.bilah__persen[aria-pressed='true'] {
  background: var(--navy-50);
  color: var(--navy);
}

.catatan-watermark {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 6px 16px;
  background: var(--navy-50);
  color: var(--navy);
  font-size: 0.8125rem;
  text-align: center;
}

.catatan-watermark svg {
  flex: none;
}

.catatan-watermark__pendek {
  display: none;
}

.area {
  display: flex;
  flex: 1;
  align-items: flex-start;
  justify-content: safe center;
  overflow: auto;
  padding: 16px;
  overscroll-behavior: contain;
}

/* Halaman muat di layar: geser kiri/kanan dipakai untuk berpindah halaman, bukan untuk menggulir. */
.area--geser {
  touch-action: pan-y pinch-zoom;
}

.halaman-pdf {
  flex: none;
  margin: auto;
  background: #fff;
  box-shadow: 0 4px 18px rgba(20, 38, 77, 0.18);
}

.keadaan {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  width: min(480px, 100%);
  margin: 10vh auto 0;
  text-align: center;
}

.keadaan__aksi {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
}

.keadaan__putar {
  color: var(--navy);
  animation: putar 1s linear infinite;
}

@keyframes putar {
  to {
    transform: rotate(360deg);
  }
}

.keadaan__teks {
  color: var(--teks);
}

.kemajuan {
  overflow: hidden;
  width: 100%;
  height: 8px;
  border-radius: 4px;
  background: var(--permukaan);
}

.kemajuan span {
  display: block;
  height: 100%;
  background: var(--navy);
  transition: width 0.2s;
}

@media (max-width: 719px) {
  .bilah {
    gap: 4px 8px;
    padding: 4px 8px;
  }

  .bilah__kiri {
    flex-basis: 100%;
  }

  .bilah__kembali span {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
  }

  /* Navigasi halaman dan ukuran tampilan berbagi satu baris. */
  .bilah__halaman,
  .bilah__tampilan {
    gap: 0;
  }

  .bilah__isian input {
    width: 52px;
  }

  .bilah__dari {
    margin-left: 4px;
    font-size: 0.875rem;
  }

  .bilah__persen {
    min-width: 52px;
  }

  .catatan-watermark__panjang {
    display: none;
  }

  .catatan-watermark__pendek {
    display: inline;
  }

  .area {
    padding: 8px;
  }
}

/* Layar penuh jarang didukung untuk elemen selain video di ponsel; tombolnya disembunyikan di layar sempit. */
@media (max-width: 479px) {
  .bilah__tampilan .bilah__layar-penuh {
    display: none;
  }
}
</style>
