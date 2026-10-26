<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ChevronDown, Download, FileText, FileUp, X } from '@lucide/vue'

import { api } from '../api/klien'
import KotakPesan from '../components/KotakPesan.vue'
import NavigasiHalaman from '../components/NavigasiHalaman.vue'
import PilStatus from '../components/PilStatus.vue'
import { useAuthStore } from '../stores/auth'
import { useNotifikasiStore } from '../stores/notifikasi'
import { usePesanStore } from '../stores/pesan'
import { formatTanggal, formatUkuranBerkas } from '../utils/format'
import { KETERANGAN_ISBN, UKURAN_MAKS_NASKAH_MB, periksaBerkasNaskah, unduhNaskah } from '../utils/isbn'

// Pengajuan ISBN (FR-14, FR-15): formulir pengajuan baru dan daftar pengajuan milik pemohon.
// Tamu melihat penjelasan singkat dan diarahkan untuk masuk.
const UKURAN = 10

const auth = useAuthStore()
const notifikasi = useNotifikasiStore()
const pesan = usePesanStore()
const route = useRoute()
const router = useRouter()

// Formulir pengajuan baru
const isian = reactive({ judul: '', penulis: '', sinopsis: '', jumlah_halaman: '' })
const berkas = ref(null)
const masukanBerkas = ref(null)
const diseret = ref(false)
const galat = ref('')
const galatIsian = ref({})
const mengirim = ref(false)

// Daftar pengajuan saya
const hasil = ref(null)
const galatDaftar = ref('')
const terbuka = ref(new Set())
const mengunduh = ref(null)

const halaman = computed(() => Math.max(1, Number.parseInt(route.query.halaman, 10) || 1))
const jumlahHalaman = computed(() => (hasil.value ? Math.max(1, Math.ceil(hasil.value.count / UKURAN)) : 1))

watch(
  () => [auth.sudahMasuk, halaman.value],
  ([masuk]) => {
    if (masuk && route.name === 'isbn') muatDaftar()
  },
  { immediate: true },
)

async function muatDaftar() {
  galatDaftar.value = ''
  try {
    hasil.value = await api.get('/isbn/pengajuan/', { page: halaman.value > 1 ? halaman.value : undefined })
  } catch (e) {
    if (e.status === 404 && halaman.value > 1) {
      router.replace({ name: 'isbn' })
      return
    }
    if (e.status !== 401) galatDaftar.value = e.detail
  }
}

function tautanHalaman(n) {
  return { name: 'isbn', query: n > 1 ? { halaman: String(n) } : {} }
}

// Pesan galat sebuah isian hilang begitu isian itu diubah.
watch(
  () => ({ ...isian }),
  (baru, lama) => {
    const berubah = Object.keys(baru).filter((nama) => baru[nama] !== lama[nama] && galatIsian.value[nama])
    if (!berubah.length) return
    const sisa = { ...galatIsian.value }
    berubah.forEach((nama) => delete sisa[nama])
    galatIsian.value = sisa
  },
)

function pilihBerkas(file) {
  berkas.value = file || null
  const masalah = file ? periksaBerkasNaskah(file) : ''
  const sisa = { ...galatIsian.value }
  if (masalah) sisa.berkas_naskah = masalah
  else delete sisa.berkas_naskah
  galatIsian.value = sisa
}

function saatPilih(event) {
  pilihBerkas(event.target.files?.[0])
}

function saatJatuh(event) {
  diseret.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file) pilihBerkas(file)
}

function hapusBerkas(fokus = true) {
  berkas.value = null
  if (masukanBerkas.value) masukanBerkas.value.value = ''
  if (fokus) masukanBerkas.value?.focus()
}

function periksa() {
  const hasilPeriksa = {}
  if (!isian.judul.trim()) hasilPeriksa.judul = 'Judul naskah wajib diisi.'
  if (!isian.penulis.trim()) hasilPeriksa.penulis = 'Penulis wajib diisi.'
  if (!isian.sinopsis.trim()) hasilPeriksa.sinopsis = 'Sinopsis wajib diisi.'
  const halamanNaskah = String(isian.jumlah_halaman).trim()
  if (halamanNaskah && !/^[1-9]\d*$/.test(halamanNaskah)) {
    hasilPeriksa.jumlah_halaman = 'Jumlah halaman harus bilangan bulat minimal 1.'
  }
  const masalahBerkas = periksaBerkasNaskah(berkas.value)
  if (masalahBerkas) hasilPeriksa.berkas_naskah = masalahBerkas
  return hasilPeriksa
}

const URUTAN_ISIAN = [
  ['judul', 'isbn-judul'],
  ['penulis', 'isbn-penulis'],
  ['sinopsis', 'isbn-sinopsis'],
  ['jumlah_halaman', 'isbn-halaman'],
  ['berkas_naskah', 'isbn-naskah'],
]

async function fokusGalatPertama() {
  await nextTick()
  const pertama = URUTAN_ISIAN.find(([nama]) => galatIsian.value[nama])
  document.getElementById(pertama?.[1])?.focus()
}

function atributIsian(nama, id, petunjuk = '') {
  const keterangan = [petunjuk, galatIsian.value[nama] ? `${id}-galat` : ''].filter(Boolean).join(' ')
  return {
    'aria-invalid': galatIsian.value[nama] ? 'true' : undefined,
    'aria-describedby': keterangan || undefined,
  }
}

async function kirim() {
  if (mengirim.value) return
  galat.value = ''
  galatIsian.value = periksa()
  if (Object.keys(galatIsian.value).length) {
    fokusGalatPertama()
    return
  }
  const data = new FormData()
  data.append('judul', isian.judul.trim())
  data.append('penulis', isian.penulis.trim())
  data.append('sinopsis', isian.sinopsis.trim())
  if (String(isian.jumlah_halaman).trim()) data.append('jumlah_halaman', String(isian.jumlah_halaman).trim())
  data.append('berkas_naskah', berkas.value)
  mengirim.value = true
  try {
    const pengajuan = await api.post('/isbn/pengajuan/', data)
    pesan.tampilkan(`Pengajuan "${pengajuan.judul}" terkirim. Statusnya bisa dipantau di daftar Pengajuan saya.`, {
      jenis: 'sukses',
    })
    Object.assign(isian, { judul: '', penulis: '', sinopsis: '', jumlah_halaman: '' })
    hapusBerkas(false)
    galatIsian.value = {}
    terbuka.value = new Set([pengajuan.id])
    notifikasi.muat()
    if (halaman.value > 1) router.push({ name: 'isbn' })
    else await muatDaftar()
    await nextTick()
    document.getElementById(`pengajuan-${pengajuan.id}`)?.scrollIntoView({ block: 'nearest' })
  } catch (e) {
    if (e.status === 401) return
    if (Object.keys(e.isian || {}).length) {
      galatIsian.value = e.isian
      fokusGalatPertama()
      return
    }
    galat.value = e.detail || 'Pengajuan tidak dapat dikirim. Coba lagi beberapa saat.'
    await nextTick()
    document.getElementById('isbn-galat')?.focus()
  } finally {
    mengirim.value = false
  }
}

function alihDetail(id, event) {
  const salinan = new Set(terbuka.value)
  if (event.target.open) salinan.add(id)
  else salinan.delete(id)
  terbuka.value = salinan
}

async function unduh(p) {
  if (mengunduh.value) return
  mengunduh.value = p.id
  try {
    await unduhNaskah(p.id)
  } catch (e) {
    if (e.status !== 401) pesan.tampilkan(e.detail || 'Naskah tidak dapat diunduh.', { jenis: 'galat' })
  } finally {
    mengunduh.value = null
  }
}
</script>

<template>
  <div class="wadah halaman">
    <div class="halaman__kepala">
      <h1 class="halaman__judul">Pengajuan ISBN</h1>
      <p class="halaman__sub">
        Ajukan ISBN untuk naskah Anda. Admin Polibatam Press memverifikasi naskah lalu mengajukannya ke Perpusnas.
      </p>
    </div>

    <section v-if="!auth.sudahMasuk" class="kartu kartu--isi tamu" aria-labelledby="judul-tamu">
      <h2 id="judul-tamu" class="tamu__judul">Cara mengajukan ISBN</h2>
      <ol class="tamu__langkah">
        <li>Masuk atau daftar akun Polibatam Press.</li>
        <li>Isi judul, penulis, dan sinopsis, lalu unggah naskah dalam format PDF atau DOCX (maksimal 20 MB).</li>
        <li>Admin memeriksa naskah, lalu mengajukannya ke Perpusnas.</li>
        <li>Pantau statusnya di halaman ini. Nomor ISBN tampil setelah terbit, dan setiap perubahan dikabarkan lewat notifikasi.</li>
      </ol>
      <div class="tamu__aksi">
        <RouterLink :to="{ name: 'masuk', query: { next: route.fullPath } }" class="tombol tombol--utama">
          Masuk untuk mengajukan
        </RouterLink>
        <RouterLink :to="{ name: 'daftar', query: { next: route.fullPath } }" class="tombol tombol--sekunder">
          Daftar akun
        </RouterLink>
      </div>
    </section>

    <div v-else class="isbn">
      <section class="kartu kartu--isi isbn__baru" aria-labelledby="judul-baru">
        <h2 id="judul-baru" class="isbn__subjudul">Pengajuan baru</h2>
        <div v-if="galat" id="isbn-galat" tabindex="-1" class="isbn__galat">
          <KotakPesan jenis="galat">{{ galat }}</KotakPesan>
        </div>
        <form class="formulir" novalidate @submit.prevent="kirim">
          <div class="isian">
            <label for="isbn-judul" class="isian__label">Judul naskah</label>
            <input
              id="isbn-judul"
              v-model="isian.judul"
              type="text"
              class="isian__kontrol"
              maxlength="255"
              v-bind="atributIsian('judul', 'isbn-judul')"
            >
            <p v-if="galatIsian.judul" id="isbn-judul-galat" class="isian__galat">{{ galatIsian.judul }}</p>
          </div>
          <div class="isian">
            <label for="isbn-penulis" class="isian__label">Penulis</label>
            <input
              id="isbn-penulis"
              v-model="isian.penulis"
              type="text"
              class="isian__kontrol"
              maxlength="255"
              v-bind="atributIsian('penulis', 'isbn-penulis', 'isbn-penulis-petunjuk')"
            >
            <p id="isbn-penulis-petunjuk" class="isian__petunjuk">Pisahkan beberapa penulis dengan titik koma.</p>
            <p v-if="galatIsian.penulis" id="isbn-penulis-galat" class="isian__galat">{{ galatIsian.penulis }}</p>
          </div>
          <div class="isian">
            <label for="isbn-sinopsis" class="isian__label">Sinopsis</label>
            <textarea
              id="isbn-sinopsis"
              v-model="isian.sinopsis"
              class="isian__kontrol"
              rows="5"
              v-bind="atributIsian('sinopsis', 'isbn-sinopsis')"
            />
            <p v-if="galatIsian.sinopsis" id="isbn-sinopsis-galat" class="isian__galat">{{ galatIsian.sinopsis }}</p>
          </div>
          <div class="isian isbn__halaman">
            <label for="isbn-halaman" class="isian__label">Jumlah halaman (opsional)</label>
            <input
              id="isbn-halaman"
              v-model="isian.jumlah_halaman"
              type="number"
              inputmode="numeric"
              min="1"
              class="isian__kontrol"
              v-bind="atributIsian('jumlah_halaman', 'isbn-halaman')"
            >
            <p v-if="galatIsian.jumlah_halaman" id="isbn-halaman-galat" class="isian__galat">
              {{ galatIsian.jumlah_halaman }}
            </p>
          </div>

          <div class="isian">
            <span id="isbn-naskah-label" class="isian__label">Berkas naskah</span>
            <label
              class="unggah"
              :class="{ 'is-diseret': diseret, 'is-galat': galatIsian.berkas_naskah }"
              @dragover.prevent="diseret = true"
              @dragleave="diseret = false"
              @drop.prevent="saatJatuh"
            >
              <FileUp :size="28" class="unggah__ikon" aria-hidden="true" />
              <span class="unggah__teks">{{ berkas ? 'Ganti berkas' : 'Pilih berkas atau seret ke sini' }}</span>
              <span id="isbn-naskah-petunjuk" class="unggah__petunjuk">PDF atau DOCX, maksimal {{ UKURAN_MAKS_NASKAH_MB }} MB</span>
              <input
                id="isbn-naskah"
                ref="masukanBerkas"
                type="file"
                class="unggah__masukan"
                accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                aria-labelledby="isbn-naskah-label"
                v-bind="atributIsian('berkas_naskah', 'isbn-naskah', 'isbn-naskah-petunjuk')"
                @change="saatPilih"
              >
            </label>
            <div v-if="berkas" class="berkas-terpilih">
              <FileText :size="20" aria-hidden="true" />
              <span class="berkas-terpilih__nama">{{ berkas.name }}</span>
              <span class="berkas-terpilih__ukuran">{{ formatUkuranBerkas(berkas.size) }}</span>
              <button type="button" class="tombol-ikon" :aria-label="`Hapus berkas ${berkas.name}`" @click="hapusBerkas()">
                <X :size="18" />
              </button>
            </div>
            <p v-if="galatIsian.berkas_naskah" id="isbn-naskah-galat" class="isian__galat">{{ galatIsian.berkas_naskah }}</p>
          </div>

          <button type="submit" class="tombol tombol--utama tombol--besar" :disabled="mengirim">
            {{ mengirim ? 'Mengirim…' : 'Kirim pengajuan' }}
          </button>
          <p class="isian__petunjuk">Maksimal 5 pengajuan yang belum selesai pada saat yang sama.</p>
        </form>
      </section>

      <section class="isbn__saya" aria-labelledby="judul-saya">
        <h2 id="judul-saya" class="isbn__subjudul">Pengajuan saya</h2>

        <KotakPesan v-if="galatDaftar" jenis="galat">
          <span>{{ galatDaftar }}</span>
          <button type="button" class="tombol tombol--sekunder" @click="muatDaftar">Coba lagi</button>
        </KotakPesan>

        <div v-else-if="!hasil" aria-busy="true" aria-label="Memuat pengajuan">
          <div v-for="n in 3" :key="n" class="kerangka" style="height: 72px; margin-bottom: 10px" />
        </div>

        <div v-else-if="!hasil.count" class="kartu kartu--isi isbn__kosong">
          <FileText :size="32" aria-hidden="true" />
          <p>Belum ada pengajuan. Pengajuan yang Anda kirim akan tampil di sini beserta statusnya.</p>
        </div>

        <template v-else>
          <div class="daftar-pengajuan">
            <details
              v-for="p in hasil.results"
              :id="`pengajuan-${p.id}`"
              :key="p.id"
              class="pengajuan"
              :open="terbuka.has(p.id)"
              @toggle="alihDetail(p.id, $event)"
            >
              <summary class="pengajuan__ringkas">
                <span class="pengajuan__teks">
                  <span class="pengajuan__judul">{{ p.judul }}</span>
                  <span class="pengajuan__meta">
                    <PilStatus jenis="isbn" :status="p.status" :label="p.status_label" />
                    Diajukan {{ formatTanggal(p.diajukan) }}
                  </span>
                </span>
                <ChevronDown :size="20" class="pengajuan__panah" aria-hidden="true" />
              </summary>
              <div class="pengajuan__isi">
                <dl v-if="p.status === 'selesai'" class="pengajuan__data">
                  <div>
                    <dt>Nomor ISBN</dt>
                    <dd class="pengajuan__isbn">{{ p.nomor_isbn }}</dd>
                  </div>
                  <div v-if="p.tanggal_penetapan">
                    <dt>Tanggal penetapan</dt>
                    <dd>{{ formatTanggal(p.tanggal_penetapan) }}</dd>
                  </div>
                </dl>
                <template v-else-if="p.status === 'ditolak'">
                  <p class="pengajuan__label">Alasan penolakan</p>
                  <p class="pengajuan__alasan">{{ p.alasan_penolakan }}</p>
                  <p class="pengajuan__catatan">{{ KETERANGAN_ISBN.ditolak }}</p>
                </template>
                <p v-else class="pengajuan__catatan">{{ KETERANGAN_ISBN[p.status] }}</p>
                <div class="pengajuan__aksi">
                  <RouterLink :to="{ name: 'isbn-detail', params: { id: p.id } }" class="tombol tombol--sekunder tombol--kecil">
                    Lihat detail
                  </RouterLink>
                  <button
                    type="button"
                    class="tombol tombol--sekunder tombol--kecil"
                    :aria-disabled="mengunduh ? 'true' : undefined"
                    @click="unduh(p)"
                  >
                    <Download :size="16" aria-hidden="true" />
                    {{ mengunduh === p.id ? 'Menyiapkan…' : 'Unduh naskah' }}
                  </button>
                </div>
              </div>
            </details>
          </div>
          <NavigasiHalaman :halaman="halaman" :jumlah="jumlahHalaman" :tautan="tautanHalaman" label="Halaman pengajuan" />
        </template>
      </section>
    </div>
  </div>
</template>

<style scoped>
.isbn {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  align-items: start;
  gap: 24px;
}

.isbn__subjudul {
  margin-bottom: 16px;
  font-size: 1.25rem;
}

.isbn__galat {
  margin-bottom: 16px;
}

.isbn__galat:focus {
  outline: none;
}

.isbn__halaman {
  max-width: 240px;
}

.unggah {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 24px 16px;
  border: 2px dashed var(--garis-isian);
  border-radius: var(--radius);
  background: var(--latar);
  text-align: center;
  cursor: pointer;
}

.unggah:hover,
.unggah.is-diseret {
  border-color: var(--navy);
  background: var(--navy-50);
}

.unggah.is-galat {
  border-color: var(--galat);
}

.unggah:focus-within {
  outline: 3px solid var(--navy);
  outline-offset: 2px;
}

.unggah__ikon {
  color: var(--navy);
}

.unggah__teks {
  color: var(--navy);
  font-weight: 700;
}

.unggah__petunjuk {
  color: var(--teks-redup);
  font-size: 0.8125rem;
}

/* Masukan berkas asli tetap bisa difokus dan dibaca pembaca layar, tetapi tidak terlihat. */
.unggah__masukan {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}

.berkas-terpilih {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 6px 6px 12px;
  border: 1px solid var(--garis);
  border-radius: var(--radius-kecil);
  background: var(--permukaan);
  color: var(--navy);
}

.berkas-terpilih__nama {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  color: var(--teks);
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.berkas-terpilih__ukuran {
  flex: none;
  color: var(--teks-redup);
  font-size: 0.8125rem;
}

.isbn__kosong {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: var(--teks-redup);
  text-align: center;
}

.daftar-pengajuan {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 8px;
}

.pengajuan {
  border: 1px solid var(--garis);
  border-radius: var(--radius-besar);
  background: var(--permukaan);
}

.pengajuan__ringkas {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 44px;
  padding: 14px 16px;
  cursor: pointer;
  list-style: none;
}

.pengajuan__ringkas::-webkit-details-marker {
  display: none;
}

.pengajuan__ringkas:focus-visible {
  border-radius: var(--radius-besar);
  outline-offset: -3px;
}

.pengajuan__teks {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.pengajuan__judul {
  font-weight: 700;
  overflow-wrap: anywhere;
}

.pengajuan__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 10px;
  color: var(--teks-redup);
  font-size: 0.8125rem;
}

.pengajuan__panah {
  flex: none;
  color: var(--teks-redup);
  transition: transform 0.15s;
}

.pengajuan[open] .pengajuan__panah {
  transform: rotate(180deg);
}

.pengajuan__isi {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 0 16px 16px;
}

.pengajuan__data {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 32px;
  margin: 0;
}

.pengajuan__data dt {
  color: var(--teks-redup);
  font-size: 0.8125rem;
}

.pengajuan__data dd {
  margin: 0;
  font-weight: 600;
}

.pengajuan__isbn {
  color: var(--navy);
  font-size: 1.125rem;
  font-variant-numeric: tabular-nums;
}

.pengajuan__label {
  color: var(--teks-redup);
  font-size: 0.8125rem;
}

.pengajuan__alasan {
  padding: 10px 12px;
  border-left: 3px solid var(--galat);
  border-radius: var(--radius-kecil);
  background: var(--galat-50);
  white-space: pre-line;
}

.pengajuan__catatan {
  color: var(--teks-redup);
  font-size: 0.875rem;
}

.pengajuan__aksi {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 4px;
}

.tombol--kecil {
  min-height: 44px;
  padding: 0 14px;
}

.tamu {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 720px;
}

.tamu__judul {
  font-size: 1.25rem;
}

.tamu__langkah {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 0;
  padding-left: 20px;
}

.tamu__aksi {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

@media (max-width: 959px) {
  .isbn {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
