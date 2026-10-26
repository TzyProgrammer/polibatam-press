<script setup>
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { Check, Copy, Download, X } from '@lucide/vue'

import { api } from '../api/klien'
import KotakPesan from '../components/KotakPesan.vue'
import PilStatus from '../components/PilStatus.vue'
import { usePesanStore } from '../stores/pesan'
import { formatTanggal, formatTanggalJam } from '../utils/format'
import { KETERANGAN_ISBN, unduhNaskah } from '../utils/isbn'

// Detail satu pengajuan ISBN milik pemohon (tautan notifikasi /isbn/<id>).
const route = useRoute()
const pesan = usePesanStore()

const pengajuan = ref(null)
const galat = ref('')
const tidakAda = ref(false)
const mengunduh = ref(false)

const id = computed(() => route.params.id)

const tahap = computed(() => {
  const p = pengajuan.value
  if (!p) return []
  if (p.status === 'ditolak') {
    return [
      { kode: 'diajukan', label: 'Diajukan', keadaan: 'selesai' },
      { kode: 'ditolak', label: 'Ditolak', keadaan: 'ditolak' },
    ]
  }
  const urutan = ['menunggu_verifikasi', 'diproses', 'selesai']
  const label = { menunggu_verifikasi: 'Menunggu verifikasi', diproses: 'Diproses', selesai: 'Selesai' }
  const posisi = urutan.indexOf(p.status)
  return urutan.map((kode, i) => ({
    kode,
    label: label[kode],
    keadaan: i < posisi || (i === posisi && kode === 'selesai') ? 'selesai' : i === posisi ? 'aktif' : 'nanti',
  }))
})

async function muat(nilai) {
  galat.value = ''
  tidakAda.value = false
  try {
    const data = await api.get(`/isbn/pengajuan/${encodeURIComponent(nilai)}/`)
    if (nilai !== id.value) return
    pengajuan.value = data
    document.title = `${data.judul} · Pengajuan ISBN · Polibatam Press`
  } catch (e) {
    if (nilai !== id.value) return
    pengajuan.value = null
    if (e.status === 404) tidakAda.value = true
    else if (e.status !== 401) galat.value = e.detail
  }
}

watch(
  id,
  (nilai) => {
    if (nilai && route.name === 'isbn-detail') {
      pengajuan.value = null
      muat(nilai)
    }
  },
  { immediate: true },
)

async function unduh() {
  if (mengunduh.value || !pengajuan.value) return
  mengunduh.value = true
  try {
    await unduhNaskah(pengajuan.value.id)
  } catch (e) {
    if (e.status !== 401) pesan.tampilkan(e.detail || 'Naskah tidak dapat diunduh.', { jenis: 'galat' })
  } finally {
    mengunduh.value = false
  }
}

async function salinIsbn() {
  try {
    await navigator.clipboard.writeText(pengajuan.value.nomor_isbn)
    pesan.tampilkan('Nomor ISBN disalin.', { jenis: 'sukses', durasi: 3000 })
  } catch {
    pesan.tampilkan('Nomor ISBN tidak dapat disalin otomatis. Salin secara manual.', { jenis: 'info' })
  }
}
</script>

<template>
  <div class="wadah halaman">
    <nav class="jejak" aria-label="Jejak navigasi">
      <ol>
        <li><RouterLink :to="{ name: 'isbn' }">Pengajuan ISBN</RouterLink></li>
        <li aria-current="page">{{ pengajuan?.judul || 'Detail pengajuan' }}</li>
      </ol>
    </nav>

    <div v-if="tidakAda" class="kartu kartu--isi kosong">
      <h1 class="halaman__judul">Pengajuan tidak ditemukan</h1>
      <p class="halaman__sub">Pengajuan ini tidak ada atau bukan milik akun Anda.</p>
      <RouterLink :to="{ name: 'isbn' }" class="tombol tombol--utama">Ke Pengajuan ISBN</RouterLink>
    </div>

    <KotakPesan v-else-if="galat" jenis="galat">
      <span>{{ galat }}</span>
      <button type="button" class="tombol tombol--sekunder" @click="muat(id)">Coba lagi</button>
    </KotakPesan>

    <div v-else-if="!pengajuan" aria-busy="true" aria-label="Memuat pengajuan">
      <div class="kerangka" style="height: 40px; width: min(520px, 100%); margin-bottom: 20px" />
      <div class="kerangka" style="height: 320px" />
    </div>

    <template v-else>
      <div class="kepala">
        <h1 class="halaman__judul kepala__judul">{{ pengajuan.judul }}</h1>
        <div class="kepala__status">
          <PilStatus jenis="isbn" :status="pengajuan.status" :label="pengajuan.status_label" />
        </div>
        <p class="kepala__meta">
          <span>Diajukan {{ formatTanggalJam(pengajuan.diajukan) }}</span> ·
          <span>Diperbarui {{ formatTanggalJam(pengajuan.diperbarui) }}</span>
        </p>
      </div>

      <div class="isbn-detail">
        <div class="isbn-detail__kiri">
          <section class="kartu kartu--isi" aria-labelledby="judul-status">
            <h2 id="judul-status" class="isbn-detail__subjudul">Status pengajuan</h2>
            <ol class="lini" aria-label="Tahap pengajuan">
              <li
                v-for="t in tahap"
                :key="t.kode"
                class="lini__item"
                :class="`is-${t.keadaan}`"
                :aria-current="t.kode === pengajuan.status ? 'step' : undefined"
              >
                <span class="lini__tanda" aria-hidden="true">
                  <Check v-if="t.keadaan === 'selesai'" :size="14" :stroke-width="3" />
                  <X v-else-if="t.keadaan === 'ditolak'" :size="14" :stroke-width="3" />
                </span>
                <span class="lini__label">{{ t.label }}</span>
              </li>
            </ol>

            <div v-if="pengajuan.status === 'selesai'" class="hasil hasil--selesai">
              <p class="hasil__label">Nomor ISBN</p>
              <div class="hasil__isbn">
                <span>{{ pengajuan.nomor_isbn }}</span>
                <button type="button" class="tombol-ikon" aria-label="Salin nomor ISBN" @click="salinIsbn">
                  <Copy :size="18" />
                </button>
              </div>
              <p v-if="pengajuan.tanggal_penetapan" class="hasil__catatan">
                Ditetapkan {{ formatTanggal(pengajuan.tanggal_penetapan) }}
              </p>
            </div>
            <div v-else-if="pengajuan.status === 'ditolak'" class="hasil hasil--ditolak">
              <p class="hasil__label">Alasan penolakan</p>
              <p class="hasil__alasan">{{ pengajuan.alasan_penolakan }}</p>
              <p class="hasil__catatan">
                Perbaiki naskah lalu kirim sebagai
                <RouterLink :to="{ name: 'isbn' }">pengajuan baru</RouterLink>.
              </p>
            </div>
            <p v-else class="isbn-detail__keterangan">{{ KETERANGAN_ISBN[pengajuan.status] }}</p>
          </section>

          <section class="kartu kartu--isi" aria-labelledby="judul-naskah">
            <h2 id="judul-naskah" class="isbn-detail__subjudul">Data naskah</h2>
            <dl class="data">
              <div>
                <dt>Penulis</dt>
                <dd>{{ pengajuan.penulis }}</dd>
              </div>
              <div v-if="pengajuan.jumlah_halaman">
                <dt>Jumlah halaman</dt>
                <dd>{{ pengajuan.jumlah_halaman }} halaman</dd>
              </div>
              <div>
                <dt>Sinopsis</dt>
                <dd class="data__sinopsis">{{ pengajuan.sinopsis }}</dd>
              </div>
            </dl>
          </section>
        </div>

        <aside class="kartu kartu--isi isbn-detail__berkas" aria-labelledby="judul-berkas">
          <h2 id="judul-berkas" class="isbn-detail__subjudul">Berkas naskah</h2>
          <template v-if="pengajuan.naskah">
            <p class="berkas__nama">{{ pengajuan.naskah.nama }}</p>
            <p class="berkas__format">Format {{ pengajuan.naskah.format.toUpperCase() }}</p>
            <button type="button" class="tombol tombol--sekunder tombol--penuh" :aria-disabled="mengunduh ? 'true' : undefined" @click="unduh">
              <Download :size="18" aria-hidden="true" />
              {{ mengunduh ? 'Menyiapkan…' : 'Unduh naskah' }}
            </button>
          </template>
          <p v-else class="isbn-detail__keterangan">Berkas naskah tidak tersedia.</p>
          <p class="berkas__catatan">Naskah hanya bisa diunduh oleh Anda dan admin Polibatam Press.</p>
        </aside>
      </div>
    </template>
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

.kepala {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 20px;
}

.kepala__judul {
  overflow-wrap: anywhere;
}

.kepala__status {
  display: flex;
  gap: 8px;
}

.kepala__meta {
  color: var(--teks-redup);
  font-size: 0.9375rem;
}

/* Di layar sempit baris dipotong di antara "Diajukan …" dan "Diperbarui …", bukan di tengah tanggal. */
.kepala__meta span {
  white-space: nowrap;
}

.isbn-detail {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  align-items: start;
  gap: 24px;
}

.isbn-detail__kiri {
  display: flex;
  flex-direction: column;
  gap: 24px;
  min-width: 0;
}

.isbn-detail__subjudul {
  margin-bottom: 16px;
  font-size: 1.125rem;
}

.isbn-detail__keterangan {
  margin-top: 20px;
  color: var(--teks-redup);
}

.isbn-detail__berkas {
  position: sticky;
  top: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* Lini tahap */
.lini {
  display: grid;
  grid-auto-columns: minmax(0, 1fr);
  grid-auto-flow: column;
  margin: 0;
  padding: 0;
  list-style: none;
}

.lini__item {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  color: var(--teks-redup);
  font-size: 0.875rem;
  font-weight: 600;
  text-align: center;
}

.lini__item:not(:first-child)::before {
  content: '';
  position: absolute;
  top: 11px;
  right: calc(50% + 16px);
  left: calc(-50% + 16px);
  height: 2px;
  border-radius: 1px;
  background: var(--garis);
}

.lini__item.is-selesai::before,
.lini__item.is-aktif::before,
.lini__item.is-ditolak::before {
  background: var(--navy);
}

.lini__tanda {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: 2px solid var(--garis-isian);
  border-radius: 50%;
  background: var(--permukaan);
}

.is-selesai .lini__tanda {
  border-color: var(--navy);
  background: var(--navy);
  color: #fff;
}

.is-aktif .lini__tanda {
  border-color: var(--navy);
  box-shadow: inset 0 0 0 4px var(--permukaan);
  background: var(--navy);
}

.is-ditolak .lini__tanda {
  border-color: var(--galat);
  background: var(--galat);
  color: #fff;
}

.is-selesai,
.is-aktif {
  color: var(--navy);
}

.is-ditolak {
  color: var(--galat);
}

/* Hasil */
.hasil {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 20px;
  padding: 14px 16px;
  border-radius: var(--radius);
}

.hasil--selesai {
  border: 1px solid #abefc6;
  background: var(--sukses-50);
}

.hasil--ditolak {
  border: 1px solid #f4c7c3;
  background: var(--galat-50);
}

.hasil__label {
  color: var(--teks-redup);
  font-size: 0.8125rem;
  font-weight: 600;
}

/* Nomor ISBN tidak pernah dipenggal; di ponsel hurufnya mengecil, dan bila tetap tidak muat, tombol salin
   yang turun ke baris berikutnya. */
.hasil__isbn {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  color: var(--sukses);
  font-family: var(--font-judul);
  font-size: clamp(1.25rem, 4vw + 0.25rem, 1.5rem);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.hasil__isbn span {
  white-space: nowrap;
}

.hasil__isbn .tombol-ikon {
  color: var(--sukses);
}

.hasil__alasan {
  white-space: pre-line;
}

.hasil__catatan {
  color: var(--teks-redup);
  font-size: 0.875rem;
}

/* Data naskah */
.data {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin: 0;
}

.data div {
  display: grid;
  grid-template-columns: 160px minmax(0, 1fr);
  gap: 12px;
}

.data dt {
  color: var(--teks-redup);
}

.data dd {
  margin: 0;
  overflow-wrap: anywhere;
}

.data__sinopsis {
  white-space: pre-line;
}

.berkas__nama {
  font-weight: 700;
  overflow-wrap: anywhere;
}

.berkas__format,
.berkas__catatan {
  color: var(--teks-redup);
  font-size: 0.875rem;
}

.berkas__catatan {
  margin-top: 4px;
}

.kosong {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
}

@media (max-width: 959px) {
  .isbn-detail {
    grid-template-columns: minmax(0, 1fr);
  }

  .isbn-detail__berkas {
    position: static;
  }
}

@media (max-width: 719px) {
  .data div {
    grid-template-columns: minmax(0, 1fr);
    gap: 2px;
  }
}
</style>
