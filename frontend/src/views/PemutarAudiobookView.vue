<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { LoaderCircle, Pause, Play, RotateCcw, RotateCw, ShieldCheck, Volume2, VolumeX } from '@lucide/vue'

import { api } from '../api/klien'
import KotakPesan from '../components/KotakPesan.vue'
import SampulBuku from '../components/SampulBuku.vue'
import { useAuthStore } from '../stores/auth'
import { formatDurasi, formatSisaWaktu } from '../utils/format'
import { bacaPosisi, simpanPosisi } from '../utils/posisi'

// Pemutar audiobook: POST /api/drm/audiobook/<produk_id>/sesi/ memberi URL playlist sesi. hls.js meminta
// playlist dan kunci AES-128 ke API dengan header Authorization (access token disegarkan dulu bila hampir
// habis), sedangkan segmen terenkripsi diambil dari bucket lewat presigned URL tanpa header itu.
// Sesi dibuat saat pembeli menekan Putar, bukan saat halaman dibuka.
const KECEPATAN = [0.75, 1, 1.25, 1.5, 2]
const LOMPAT_DETIK = 15
const SIMPAN_TIAP_MS = 5000

const route = useRoute()
const auth = useAuthStore()

const produkId = Number.parseInt(route.params.produkId, 10)
const info = ref(null)
const tahap = ref('memuat') // memuat | siap | memulai | aktif | galat | tidak-ada
const galat = ref('')
const audio = ref(null)
const diputar = ref(false)
const menyangga = ref(false)
const posisi = ref(0)
const posisiSeret = ref(null)
const durasi = ref(0)
const kecepatan = ref(1)
const volume = ref(1)
const bisu = ref(false)

let Hls = null
let hls = null
let aktif = true
let pulihJaringan = 0
let pulihMedia = false
let terakhirSimpan = 0

const tampilPosisi = computed(() => (posisiSeret.value ?? posisi.value))
const totalDetik = computed(() => durasi.value || info.value?.durasi_detik || 0)
const bisaDiputar = computed(() => Boolean(info.value?.aktif) && info.value?.status === 'siap')
const teksPosisi = computed(
  () => `${formatDurasi(tampilPosisi.value)} dari ${totalDetik.value ? formatDurasi(totalDetik.value) : 'durasi belum diketahui'}`,
)

function urlApi(url) {
  try {
    const tujuan = new URL(url, window.location.href)
    return tujuan.origin === window.location.origin && tujuan.pathname.startsWith('/api/')
  } catch {
    return false
  }
}

async function muatInfo() {
  tahap.value = 'memuat'
  galat.value = ''
  try {
    const data = await api.get('/koleksi/')
    if (!aktif) return
    info.value = data.find((k) => k.produk_id === produkId && k.format === 'audiobook') || null
    if (!info.value) {
      tahap.value = 'tidak-ada'
      return
    }
    document.title = `${info.value.buku.judul} · Polibatam Press`
    durasi.value = info.value.durasi_detik || 0
    posisi.value = Math.min(bacaPosisi('audiobook', produkId, auth.pengguna?.id), Math.max(0, durasi.value - 5))
    tahap.value = 'siap'
    aturMediaSession()
  } catch (e) {
    if (!aktif || e.status === 401) return
    tahap.value = 'galat'
    galat.value = e.detail
  }
}

function hancurkanHls() {
  if (hls) {
    hls.destroy()
    hls = null
  }
}

async function bukaSesi(mulaiDari) {
  // Build ringan hls.js (tanpa EME, subtitle, dan audio alternatif) sudah mencakup dekripsi AES-128.
  if (!Hls) Hls = (await import('hls.js/light')).default
  if (!Hls.isSupported()) {
    throw Object.assign(new Error('tidak didukung'), {
      detail: 'Peramban ini tidak mendukung pemutaran audiobook. Gunakan Chrome, Edge, Firefox, atau Safari versi terbaru.',
    })
  }
  const sesi = await api.post(`/drm/audiobook/${produkId}/sesi/`)
  if (!aktif) return
  hancurkanHls()
  pulihMedia = false
  hls = new Hls({
    startPosition: mulaiDari > 1 ? mulaiDari : -1,
    // Header Authorization hanya untuk URL API (playlist dan kunci). Presigned URL segmen tidak boleh
    // diberi header ini karena tanda tangan S3 akan ditolak.
    xhrSetup: async (xhr, url) => {
      if (!urlApi(url)) return
      const akses = await auth.aksesSegar()
      xhr.open('GET', url, true)
      if (akses) xhr.setRequestHeader('Authorization', `Bearer ${akses}`)
    },
  })
  hls.on(Hls.Events.MANIFEST_PARSED, () => {
    audio.value?.play().catch(() => {
      // Peramban menahan pemutaran otomatis (misalnya Safari): pembeli cukup menekan Putar lagi.
    })
  })
  hls.on(Hls.Events.ERROR, saatGalatHls)
  hls.loadSource(sesi.playlist)
  hls.attachMedia(audio.value)
  tahap.value = 'aktif'
}

async function mulai() {
  if (!bisaDiputar.value || tahap.value === 'memulai') return
  tahap.value = 'memulai'
  galat.value = ''
  pulihJaringan = 0
  try {
    await bukaSesi(posisi.value)
  } catch (e) {
    if (!aktif || e.status === 401) return
    tahap.value = 'galat'
    galat.value = e.detail || 'Audiobook tidak dapat diputar. Coba lagi beberapa saat.'
  }
}

function berhentiDenganGalat(pesan) {
  hancurkanHls()
  diputar.value = false
  menyangga.value = false
  tahap.value = 'galat'
  galat.value = pesan
}

function pesanJaringan(kode) {
  if (kode === 403) return 'Hak akses Anda ke audiobook ini sudah dicabut atau sesi ini bukan milik Anda.'
  if (kode === 409) return 'Audiobook sedang diproses ulang. Coba lagi beberapa saat.'
  if (kode === 401) return 'Sesi login Anda sudah berakhir. Silakan masuk kembali.'
  return 'Audio tidak dapat dimuat. Periksa koneksi Anda lalu coba lagi.'
}

function saatGalatHls(_, data) {
  if (!data.fatal || !aktif) return
  const kode = data.response?.code || data.networkDetails?.status || 0
  if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
    if (['bufferAddCodecError', 'bufferIncompatibleCodecsError', 'manifestIncompatibleCodecsError'].includes(data.details)) {
      berhentiDenganGalat('Peramban ini tidak dapat memutar format audio AAC. Gunakan Chrome, Edge, Firefox, atau Safari versi terbaru.')
      return
    }
    if (!pulihMedia) {
      pulihMedia = true
      hls.recoverMediaError()
      return
    }
    berhentiDenganGalat('Audio tidak dapat diputar. Muat ulang halaman lalu coba lagi.')
    return
  }
  // Galat jaringan: sesi kedaluwarsa atau dicabut (410), segmen kedaluwarsa, atau koneksi terputus.
  // Coba sekali dengan sesi baru dari posisi terakhir; bila gagal lagi, tampilkan pesan.
  if (pulihJaringan < 1 && kode !== 403 && kode !== 409) {
    pulihJaringan += 1
    const dari = audio.value?.currentTime || posisi.value
    bukaSesi(dari).catch((e) => berhentiDenganGalat(e.detail || pesanJaringan(e.status)))
    return
  }
  berhentiDenganGalat(pesanJaringan(kode))
}

function alihPutar() {
  if (tahap.value === 'siap' || tahap.value === 'galat') {
    mulai()
    return
  }
  if (tahap.value !== 'aktif' || !audio.value) return
  if (audio.value.paused) audio.value.play().catch(() => {})
  else audio.value.pause()
}

function lompat(detik) {
  if (tahap.value !== 'aktif' || !audio.value) return
  const batas = Number.isFinite(audio.value.duration) ? audio.value.duration : totalDetik.value
  audio.value.currentTime = Math.min(Math.max(0, audio.value.currentTime + detik), Math.max(0, batas - 0.5))
}

function seretPosisi(event) {
  posisiSeret.value = Number(event.target.value)
}

function terapkanPosisi(event) {
  const nilai = Number(event.target.value)
  posisiSeret.value = null
  posisi.value = nilai
  if (tahap.value === 'aktif' && audio.value) audio.value.currentTime = nilai
  else simpanPosisi('audiobook', produkId, auth.pengguna?.id, nilai)
}

function ubahKecepatan(event) {
  kecepatan.value = Number(event.target.value)
  if (audio.value) audio.value.playbackRate = kecepatan.value
}

function ubahVolume(event) {
  volume.value = Number(event.target.value) / 100
  bisu.value = volume.value === 0
  if (audio.value) {
    audio.value.volume = volume.value
    audio.value.muted = bisu.value
  }
}

function alihBisu() {
  bisu.value = !bisu.value
  if (!bisu.value && volume.value === 0) volume.value = 0.5
  if (audio.value) {
    audio.value.muted = bisu.value
    audio.value.volume = volume.value
  }
}

// Kejadian elemen <audio>
function saatWaktu() {
  if (!audio.value || posisiSeret.value !== null) return
  posisi.value = audio.value.currentTime
  if (Date.now() - terakhirSimpan > SIMPAN_TIAP_MS) {
    terakhirSimpan = Date.now()
    simpanPosisi('audiobook', produkId, auth.pengguna?.id, Math.floor(posisi.value))
  }
}

function saatDurasi() {
  if (audio.value && Number.isFinite(audio.value.duration)) durasi.value = audio.value.duration
}

function saatPutar() {
  diputar.value = true
  if (audio.value) audio.value.playbackRate = kecepatan.value
}

function saatJeda() {
  diputar.value = false
  if (audio.value) simpanPosisi('audiobook', produkId, auth.pengguna?.id, Math.floor(audio.value.currentTime))
}

function saatSelesai() {
  diputar.value = false
  simpanPosisi('audiobook', produkId, auth.pengguna?.id, 0)
}

// Kontrol media di sistem operasi (layar kunci ponsel, tombol media keyboard).
function aturMediaSession() {
  if (!('mediaSession' in navigator) || !info.value) return
  const buku = info.value.buku
  navigator.mediaSession.metadata = new window.MediaMetadata({
    title: buku.judul,
    artist: buku.penulis,
    album: 'Polibatam Press',
    artwork: buku.sampul ? [{ src: buku.sampul }] : [],
  })
  const tangan = {
    play: () => alihPutar(),
    pause: () => audio.value?.pause(),
    seekbackward: () => lompat(-LOMPAT_DETIK),
    seekforward: () => lompat(LOMPAT_DETIK),
  }
  for (const [aksi, fungsi] of Object.entries(tangan)) {
    try {
      navigator.mediaSession.setActionHandler(aksi, fungsi)
    } catch {
      // Aksi tidak didukung peramban ini.
    }
  }
}

function bersihkanMediaSession() {
  if (!('mediaSession' in navigator)) return
  navigator.mediaSession.metadata = null
  for (const aksi of ['play', 'pause', 'seekbackward', 'seekforward']) {
    try {
      navigator.mediaSession.setActionHandler(aksi, null)
    } catch {
      // abaikan
    }
  }
}

onMounted(muatInfo)

onBeforeUnmount(() => {
  aktif = false
  if (audio.value && tahap.value === 'aktif') {
    simpanPosisi('audiobook', produkId, auth.pengguna?.id, Math.floor(audio.value.currentTime))
    audio.value.pause()
  }
  hancurkanHls()
  bersihkanMediaSession()
})
</script>

<template>
  <div class="wadah halaman">
    <nav class="jejak" aria-label="Jejak navigasi">
      <ol>
        <li><RouterLink :to="{ name: 'koleksi' }">Koleksi</RouterLink></li>
        <li aria-current="page">{{ info?.buku.judul || 'Audiobook' }}</li>
      </ol>
    </nav>

    <div v-if="tahap === 'memuat'" class="kartu kartu--isi pemutar" aria-busy="true" aria-label="Memuat audiobook">
      <div class="kerangka pemutar__sampul" />
      <div class="pemutar__info">
        <div class="kerangka" style="height: 32px; width: 70%" />
        <div class="kerangka" style="height: 18px; width: 40%" />
        <div class="kerangka" style="height: 120px" />
      </div>
    </div>

    <div v-else-if="tahap === 'tidak-ada'" class="kartu kartu--isi kosong">
      <h1 class="halaman__judul">Audiobook tidak ada di koleksi Anda</h1>
      <p class="halaman__sub">Audiobook ini belum Anda beli atau aksesnya sudah tidak tersedia.</p>
      <RouterLink :to="{ name: 'koleksi' }" class="tombol tombol--utama">Kembali ke Koleksi</RouterLink>
    </div>

    <section v-else-if="info" class="kartu kartu--isi pemutar" aria-labelledby="judul-audio">
      <SampulBuku class="pemutar__sampul" :src="info.buku.sampul || ''" :judul="info.buku.judul" segera />

      <div class="pemutar__info">
        <div class="pemutar__kepala">
          <h1 id="judul-audio" class="pemutar__judul">{{ info.buku.judul }}</h1>
          <p class="pemutar__penulis">oleh {{ info.buku.penulis }}</p>
          <span class="pemutar__format">{{ info.format_label }}</span>
        </div>

        <KotakPesan v-if="!bisaDiputar" jenis="info">
          {{
            info.aktif
              ? 'Audiobook ini sedang disiapkan. Coba lagi beberapa saat lagi.'
              : 'Akses Anda ke audiobook ini dinonaktifkan admin. Hubungi Polibatam Press bila ada pertanyaan.'
          }}
        </KotakPesan>
        <KotakPesan v-else-if="tahap === 'galat'" jenis="galat">{{ galat }}</KotakPesan>

        <div class="garis-waktu">
          <input
            class="garis-waktu__geser"
            type="range"
            min="0"
            :max="Math.max(1, Math.floor(totalDetik))"
            step="1"
            :value="Math.floor(tampilPosisi)"
            :disabled="!bisaDiputar"
            aria-label="Posisi pemutaran"
            :aria-valuetext="teksPosisi"
            :style="{ '--isi': `${totalDetik ? (tampilPosisi / totalDetik) * 100 : 0}%` }"
            @input="seretPosisi"
            @change="terapkanPosisi"
          >
          <div class="garis-waktu__angka">
            <span>{{ formatSisaWaktu(tampilPosisi) }}</span>
            <span>{{ totalDetik ? formatSisaWaktu(totalDetik) : '--:--' }}</span>
          </div>
        </div>

        <div class="kontrol">
          <button
            type="button"
            class="kontrol__lompat"
            :aria-label="`Mundur ${LOMPAT_DETIK} detik`"
            :disabled="tahap !== 'aktif'"
            @click="lompat(-LOMPAT_DETIK)"
          >
            <RotateCcw :size="22" aria-hidden="true" />
            <span aria-hidden="true">{{ LOMPAT_DETIK }}</span>
          </button>
          <button
            type="button"
            class="kontrol__putar"
            :aria-label="diputar ? 'Jeda' : 'Putar'"
            :disabled="!bisaDiputar || tahap === 'memulai'"
            @click="alihPutar"
          >
            <LoaderCircle v-if="tahap === 'memulai' || (diputar && menyangga)" :size="30" class="berputar" aria-hidden="true" />
            <Pause v-else-if="diputar" :size="30" aria-hidden="true" />
            <Play v-else :size="30" aria-hidden="true" />
          </button>
          <button
            type="button"
            class="kontrol__lompat"
            :aria-label="`Maju ${LOMPAT_DETIK} detik`"
            :disabled="tahap !== 'aktif'"
            @click="lompat(LOMPAT_DETIK)"
          >
            <span aria-hidden="true">{{ LOMPAT_DETIK }}</span>
            <RotateCw :size="22" aria-hidden="true" />
          </button>
        </div>

        <div class="pengaturan">
          <label class="pengaturan__kecepatan">
            <span>Kecepatan</span>
            <select :value="kecepatan" class="isian__kontrol" @change="ubahKecepatan">
              <option v-for="k in KECEPATAN" :key="k" :value="k">{{ String(k).replace('.', ',') }}×</option>
            </select>
          </label>
          <div class="pengaturan__volume">
            <button type="button" class="tombol-ikon" :aria-label="bisu ? 'Bunyikan' : 'Bisukan'" @click="alihBisu">
              <component :is="bisu || volume === 0 ? VolumeX : Volume2" :size="20" />
            </button>
            <input
              type="range"
              min="0"
              max="100"
              step="5"
              :value="bisu ? 0 : Math.round(volume * 100)"
              aria-label="Volume"
              @input="ubahVolume"
            >
          </div>
        </div>

        <p class="pemutar__catatan">
          <ShieldCheck :size="18" aria-hidden="true" />
          <span>Audio diputar lewat streaming terenkripsi dan tidak bisa diunduh.</span>
        </p>
        <p v-if="posisi > 5 && tahap === 'siap'" class="pemutar__lanjut">
          Diputar dari posisi terakhir Anda ({{ formatSisaWaktu(posisi) }}).
        </p>
      </div>

      <audio
        ref="audio"
        preload="none"
        @timeupdate="saatWaktu"
        @durationchange="saatDurasi"
        @play="saatPutar"
        @playing="menyangga = false"
        @waiting="menyangga = true"
        @pause="saatJeda"
        @ended="saatSelesai"
      />
    </section>

    <div v-else class="kartu kartu--isi kosong">
      <KotakPesan jenis="galat">{{ galat }}</KotakPesan>
      <button type="button" class="tombol tombol--utama" @click="muatInfo">Coba lagi</button>
    </div>
  </div>
</template>

<style scoped>
.jejak ol {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0 8px;
  margin: 0 0 8px;
  padding: 0;
  list-style: none;
  color: var(--teks-redup);
  font-size: 0.875rem;
}

.jejak li + li::before {
  content: '/';
  margin-right: 8px;
  color: var(--garis-isian);
}

.jejak a {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
}

.pemutar {
  display: grid;
  grid-template-columns: minmax(180px, 280px) minmax(0, 1fr);
  align-items: start;
  gap: 32px;
}

.pemutar__sampul {
  overflow: hidden;
  border: 1px solid var(--garis);
  border-radius: var(--radius);
}

.pemutar__info {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-width: 0;
}

.pemutar__kepala {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}

.pemutar__judul {
  font-size: 1.75rem;
  overflow-wrap: anywhere;
}

.pemutar__penulis {
  color: var(--teks-redup);
}

.pemutar__format {
  padding: 4px 12px;
  border-radius: 999px;
  background: var(--biru-50);
  color: var(--navy);
  font-size: 0.8125rem;
  font-weight: 600;
}

.garis-waktu {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.garis-waktu__geser {
  width: 100%;
  height: 44px;
  margin: 0;
  background: transparent;
  cursor: pointer;
  -webkit-appearance: none;
  appearance: none;
}

.garis-waktu__geser::-webkit-slider-runnable-track {
  height: 6px;
  border-radius: 3px;
  background: linear-gradient(to right, var(--navy) var(--isi), var(--garis) var(--isi));
}

.garis-waktu__geser::-moz-range-track {
  height: 6px;
  border-radius: 3px;
  background: linear-gradient(to right, var(--navy) var(--isi), var(--garis) var(--isi));
}

.garis-waktu__geser::-webkit-slider-thumb {
  width: 18px;
  height: 18px;
  margin-top: -6px;
  border: 0;
  border-radius: 50%;
  background: var(--navy);
  -webkit-appearance: none;
}

.garis-waktu__geser::-moz-range-thumb {
  width: 18px;
  height: 18px;
  border: 0;
  border-radius: 50%;
  background: var(--navy);
}

.garis-waktu__geser:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.garis-waktu__angka {
  display: flex;
  justify-content: space-between;
  color: var(--teks-redup);
  font-size: 0.875rem;
  font-variant-numeric: tabular-nums;
}

.kontrol {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
}

.kontrol button {
  border: 0;
  cursor: pointer;
}

.kontrol button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.kontrol__lompat {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
  min-width: 64px;
  height: 52px;
  padding: 0 8px;
  border-radius: 26px;
  background: transparent;
  color: var(--navy);
}

.kontrol__lompat:not(:disabled):hover {
  background: var(--navy-50);
}

.kontrol__lompat span {
  font-size: 0.875rem;
  font-weight: 700;
}

.kontrol__putar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: var(--navy);
  color: #fff;
}

.kontrol__putar:not(:disabled):hover {
  background: var(--navy-900);
}

.berputar {
  animation: putar 1s linear infinite;
}

@keyframes putar {
  to {
    transform: rotate(360deg);
  }
}

.pengaturan {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px 24px;
}

.pengaturan__kecepatan {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
}

.pengaturan__kecepatan .isian__kontrol {
  width: auto;
  min-width: 96px;
}

.pengaturan__volume {
  display: flex;
  align-items: center;
  gap: 4px;
}

.pengaturan__volume input {
  width: 140px;
  accent-color: var(--navy);
}

.pemutar__catatan {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: var(--radius-kecil);
  background: var(--navy-50);
  color: var(--navy);
  font-size: 0.875rem;
}

.pemutar__catatan svg {
  flex: none;
}

.pemutar__lanjut {
  color: var(--teks-redup);
  font-size: 0.875rem;
}

.kosong {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
}

@media (max-width: 719px) {
  .pemutar {
    grid-template-columns: minmax(0, 1fr);
    gap: 20px;
  }

  .pemutar__sampul {
    width: min(200px, 60%);
    margin-inline: auto;
  }

  .pemutar__judul {
    font-size: 1.375rem;
  }

  .kontrol {
    gap: 16px;
  }
}
</style>
