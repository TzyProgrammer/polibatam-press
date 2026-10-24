<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { Clock, QrCode, RefreshCw } from '@lucide/vue'

import { api } from '../api/klien'
import KotakPesan from '../components/KotakPesan.vue'
import LangkahBeli from '../components/LangkahBeli.vue'
import RingkasanPesanan from '../components/RingkasanPesanan.vue'
import { useNotifikasiStore } from '../stores/notifikasi'
import { usePesanStore } from '../stores/pesan'
import { formatRupiah, formatSisaWaktu, formatTanggalJam } from '../utils/format'
import { ambilBukaOtomatis, muatSnap } from '../utils/snap'

// Hasil dari peramban (callback Snap) hanya pemicu. Status sebenarnya selalu dibaca server dari Status API
// Midtrans lewat POST /api/pesanan/<nomor>/cek-status/ (dibatasi 20 kali per menit per pengguna).
const JEDA_PANTAU_MS = 15000
const JEDA_MIN_CEK_MS = 10000

const PESAN_MENUNGGU = {
  tutup: 'Jendela pembayaran ditutup sebelum pembayaran selesai. Anda bisa membukanya lagi sebelum batas waktu.',
  sukses: 'Pembayaran sedang dikonfirmasi Midtrans. Status di halaman ini diperbarui otomatis.',
  tunda: 'Pembayaran belum selesai. Bila Anda sudah membayar, status di halaman ini diperbarui otomatis.',
  galat: 'Pembayaran tidak berhasil diproses. Silakan coba lagi.',
  manual: 'Pembayaran belum diterima. Bila Anda baru saja membayar, tunggu sebentar lalu periksa lagi.',
}

const route = useRoute()
const router = useRouter()
const notifikasi = useNotifikasiStore()
const pesan = usePesanStore()

const pesanan = ref(null)
const galatMuat = ref('')
const tidakAda = ref(false)
const info = ref(null) // { jenis, teks, tautan? }
const memeriksa = ref(false)
const cekManual = ref(false)
const membuka = ref(false)
const snapTerbuka = ref(false)
const sekarang = ref(Date.now())

let aktif = true
let pewaktuDetik = null
let pewaktuPantau = null
let terakhirCek = 0
let cekBerikutnya = null

const nomor = computed(() => route.params.nomor)
const menunggu = computed(() => pesanan.value?.status_pembayaran === 'menunggu')
const sisaDetik = computed(() => {
  const batas = pesanan.value?.batas_bayar ? new Date(pesanan.value.batas_bayar).getTime() : 0
  return Math.max(0, Math.floor((batas - sekarang.value) / 1000))
})
// `pembayaran` dari API bernilai null bila batas bayar sudah lewat menurut jam server.
const lewatBatas = computed(() => menunggu.value && (!pesanan.value.pembayaran || sisaDetik.value <= 0))
const bisaBayar = computed(() => menunggu.value && !lewatBatas.value)
const adaDigital = computed(() => (pesanan.value?.item || []).some((i) => i.format !== 'cetak'))
const adaCetak = computed(() => (pesanan.value?.item || []).some((i) => i.format === 'cetak'))

const barisRingkasan = computed(() =>
  (pesanan.value?.item || []).map((i) => ({
    kunci: `${i.produk_id}-${i.format}`,
    judul: i.judul,
    keterangan: i.format === 'cetak' ? `${i.format_label} × ${i.jumlah}` : i.format_label,
    harga: i.subtotal,
  })),
)

const rincian = computed(() => {
  const p = pesanan.value
  if (!p) return []
  const hasil = [{ label: 'Subtotal', nilai: p.subtotal }]
  if (p.metode_pengiriman !== 'tanpa') hasil.push({ label: 'Ongkir', nilai: p.ongkir || 'Gratis' })
  return hasil
})

function hentikanPewaktu() {
  clearInterval(pewaktuDetik)
  clearInterval(pewaktuPantau)
  pewaktuDetik = null
  pewaktuPantau = null
  document.removeEventListener('visibilitychange', saatTerlihat)
}

function mulaiPewaktu() {
  hentikanPewaktu()
  sekarang.value = Date.now()
  pewaktuDetik = setInterval(() => {
    sekarang.value = Date.now()
  }, 1000)
  pewaktuPantau = setInterval(pantau, JEDA_PANTAU_MS)
  document.addEventListener('visibilitychange', saatTerlihat)
}

// Pemeriksaan berkala selama tab terlihat dan pesanan masih bisa dibayar. Dengan begitu status ikut
// berubah walaupun notifikasi Midtrans (webhook) tidak sampai, misalnya di laptop tanpa tunnel publik.
function pantau() {
  if (document.visibilityState !== 'visible' || !bisaBayar.value) return
  if (Date.now() - terakhirCek < JEDA_MIN_CEK_MS) return
  cekStatus({ diam: true })
}

function saatTerlihat() {
  if (document.visibilityState !== 'visible') return
  sekarang.value = Date.now()
  pantau()
}

async function muat(n) {
  const bukaOtomatis = ambilBukaOtomatis(n)
  hentikanPewaktu()
  pesanan.value = null
  galatMuat.value = ''
  tidakAda.value = false
  info.value = null
  snapTerbuka.value = false
  cekBerikutnya = null
  try {
    const data = await api.get(`/pesanan/${encodeURIComponent(n)}/`)
    if (!aktif || n !== nomor.value) return
    if (data.status_pembayaran !== 'menunggu') {
      router.replace({ name: 'pesanan-detail', params: { nomor: n } })
      return
    }
    pesanan.value = data
    document.title = `Pembayaran ${n} · Polibatam Press`
    mulaiPewaktu()
    // Setelah checkout jendela Snap langsung dibuka sekali; saat halaman dimuat ulang tidak.
    if (bukaOtomatis && bisaBayar.value) bayar()
  } catch (e) {
    if (!aktif || n !== nomor.value) return
    if (e.status === 404) tidakAda.value = true
    else if (e.status !== 401) galatMuat.value = e.detail
  }
}

watch(
  nomor,
  (n) => {
    if (n && route.name === 'pembayaran') muat(n)
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  aktif = false
  hentikanPewaktu()
})

function selesaiLunas(data) {
  notifikasi.muat()
  pesan.tampilkan(`Pembayaran pesanan ${data.nomor} diterima.`, { jenis: 'sukses' })
  router.replace({ name: 'pesanan-detail', params: { nomor: data.nomor } })
}

function terapkan(data, { diam, sumber }) {
  pesanan.value = data
  if (data.status_pembayaran !== 'menunggu') {
    cekBerikutnya = null
    // Bila jendela Snap masih terbuka, tunggu sampai ditutup (callback Snap memeriksa lagi).
    if (snapTerbuka.value) return
    if (data.status_pembayaran === 'lunas') selesaiLunas(data)
    else router.replace({ name: 'pesanan-detail', params: { nomor: data.nomor } })
    return
  }
  if (!diam) {
    info.value = { jenis: sumber === 'galat' ? 'galat' : 'info', teks: PESAN_MENUNGGU[sumber] || PESAN_MENUNGGU.manual }
  }
}

async function cekStatus({ diam = false, sumber = 'manual' } = {}) {
  if (!pesanan.value) return
  if (memeriksa.value) {
    // Pemeriksaan yang sedang berjalan mungkin dimulai sebelum pembeli membayar: ulangi setelahnya.
    if (!diam) cekBerikutnya = { diam, sumber }
    return
  }
  const n = pesanan.value.nomor
  memeriksa.value = true
  if (!diam) cekManual.value = true
  try {
    const data = await api.post(`/pesanan/${encodeURIComponent(n)}/cek-status/`)
    if (aktif && n === nomor.value) terapkan(data, { diam, sumber })
  } catch (e) {
    if (aktif && !diam && e.status !== 401) info.value = { jenis: 'galat', teks: e.detail }
  } finally {
    terakhirCek = Date.now()
    memeriksa.value = false
    cekManual.value = false
    if (cekBerikutnya && aktif) {
      const opsi = cekBerikutnya
      cekBerikutnya = null
      cekStatus(opsi)
    }
  }
}

function setelahSnap(sumber) {
  snapTerbuka.value = false
  if (aktif) cekStatus({ sumber })
}

async function bayar() {
  const data = pesanan.value?.pembayaran
  if (!data || !bisaBayar.value || membuka.value || snapTerbuka.value) return
  info.value = null
  membuka.value = true
  let snap
  try {
    snap = await muatSnap(data.snap_js, data.client_key)
  } catch {
    if (aktif) {
      info.value = {
        jenis: 'galat',
        teks: 'Jendela pembayaran Midtrans tidak dapat dimuat. Periksa koneksi Anda lalu coba lagi, atau buka halaman pembayaran Midtrans di tab baru.',
        tautan: data.redirect_url,
      }
    }
    return
  } finally {
    membuka.value = false
  }
  if (!aktif) return
  snapTerbuka.value = true
  try {
    // Keempat callback diisi; tanpa callback Snap mengalihkan pembeli ke Finish URL di dashboard Midtrans.
    snap.pay(data.snap_token, {
      onSuccess: () => setelahSnap('sukses'),
      onPending: () => setelahSnap('tunda'),
      onError: () => setelahSnap('galat'),
      onClose: () => setelahSnap('tutup'),
    })
  } catch {
    snapTerbuka.value = false
    info.value = {
      jenis: 'galat',
      teks: 'Jendela pembayaran tidak dapat dibuka. Muat ulang halaman ini lalu coba lagi.',
      tautan: data.redirect_url,
    }
  }
}

function cekManualSekarang() {
  if (!cekManual.value) cekStatus()
}
</script>

<template>
  <div class="wadah halaman">
    <div class="halaman__kepala">
      <h1 class="halaman__judul">Pembayaran</h1>
      <p class="halaman__sub">Pesanan sudah dibuat. Selesaikan pembayaran sebelum batas waktu.</p>
    </div>

    <div v-if="tidakAda" class="kartu kartu--isi kosong">
      <h2 class="kosong__judul">Pesanan tidak ditemukan</h2>
      <p class="kosong__teks">Pesanan ini tidak ada atau bukan milik akun Anda.</p>
      <RouterLink :to="{ name: 'pesanan' }" class="tombol tombol--utama">Ke Pesanan saya</RouterLink>
    </div>

    <KotakPesan v-else-if="galatMuat" jenis="galat">
      <span>{{ galatMuat }}</span>
      <button type="button" class="tombol tombol--sekunder" @click="muat(nomor)">Coba lagi</button>
    </KotakPesan>

    <div v-else-if="!pesanan" class="bayar" aria-busy="true" aria-label="Memuat pembayaran">
      <div class="kerangka" style="height: 460px" />
      <div class="kerangka" style="height: 320px" />
    </div>

    <template v-else>
      <LangkahBeli :aktif="3" :tanpa-pengiriman="pesanan.metode_pengiriman === 'tanpa'" />

      <div class="bayar">
        <section class="kartu kartu--isi bayar__utama" aria-labelledby="judul-status">
          <h2 id="judul-status" class="bayar__status">
            <Clock :size="22" aria-hidden="true" />
            {{ pesanan.status_pembayaran_label }}
          </h2>

          <dl class="bayar__data">
            <div>
              <dt>Nomor pesanan</dt>
              <dd class="bayar__nomor">{{ pesanan.nomor }}</dd>
            </div>
            <div>
              <dt>Total</dt>
              <dd class="bayar__total">{{ formatRupiah(pesanan.total) }}</dd>
            </div>
            <div>
              <dt>Batas bayar</dt>
              <dd>{{ formatTanggalJam(pesanan.batas_bayar) }}</dd>
            </div>
          </dl>

          <KotakPesan v-if="pesanan.status_pembayaran === 'lunas'" jenis="sukses">
            <span>Pembayaran diterima.</span>
            <RouterLink :to="{ name: 'pesanan-detail', params: { nomor: pesanan.nomor } }">Lihat detail pesanan</RouterLink>
          </KotakPesan>

          <template v-else-if="menunggu">
            <div v-if="!lewatBatas" class="bayar__waktu" role="timer" aria-label="Sisa waktu pembayaran">
              <span class="bayar__waktu-label">Sisa waktu</span>
              <span class="bayar__hitung">{{ formatSisaWaktu(sisaDetik) }}</span>
            </div>
            <KotakPesan v-else jenis="galat">
              Batas waktu pembayaran sudah lewat. Bila Anda sudah membayar sebelum batas waktu, tekan Cek status
              pembayaran. Pesanan yang tidak dibayar ditutup otomatis{{ adaCetak ? ' dan stok buku cetak dikembalikan' : '' }}.
            </KotakPesan>

            <KotakPesan v-if="info" :jenis="info.jenis">
              <span>{{ info.teks }}</span>
              <a v-if="info.tautan" :href="info.tautan" target="_blank" rel="noopener">Buka halaman pembayaran Midtrans</a>
            </KotakPesan>

            <div class="bayar__aksi">
              <button
                type="button"
                class="tombol tombol--utama tombol--besar"
                :disabled="!bisaBayar || membuka || snapTerbuka"
                @click="bayar"
              >
                <QrCode :size="20" aria-hidden="true" />
                {{ membuka ? 'Membuka…' : 'Bayar dengan QRIS' }}
              </button>
              <button
                type="button"
                class="tombol tombol--sekunder tombol--besar"
                :aria-disabled="cekManual ? 'true' : undefined"
                @click="cekManualSekarang"
              >
                <RefreshCw :size="20" aria-hidden="true" :class="{ berputar: cekManual }" />
                {{ cekManual ? 'Memeriksa…' : 'Cek status pembayaran' }}
              </button>
            </div>

            <p class="bayar__catatan">
              Status pesanan berubah setelah Midtrans mengonfirmasi pembayaran. Halaman ini memeriksanya secara berkala;
              bila belum berubah setelah membayar, tekan Cek status pembayaran.
            </p>
          </template>

          <div v-if="menunggu" class="bayar__cara">
            <h3 class="bayar__subjudul">Cara membayar</h3>
            <ol>
              <li>Tekan <strong>Bayar dengan QRIS</strong>; jendela pembayaran Midtrans terbuka.</li>
              <li>Pindai kode QR dengan aplikasi e-wallet atau mobile banking.</li>
              <li>Selesaikan pembayaran di aplikasi Anda.</li>
              <li v-if="adaDigital">Status pesanan berubah menjadi Lunas; ebook dan audiobook langsung masuk ke Koleksi.</li>
              <li v-else>Status pesanan berubah menjadi Lunas, lalu buku cetak diproses.</li>
            </ol>
          </div>
        </section>

        <RingkasanPesanan
          class="bayar__ringkasan"
          id-judul="judul-ringkasan-bayar"
          :baris="barisRingkasan"
          :rincian="rincian"
          :total="pesanan.total"
        >
          <p class="bayar__kirim">
            <span>Pengiriman</span>
            <span>{{ pesanan.metode_pengiriman_label }}</span>
          </p>
          <RouterLink
            :to="{ name: 'pesanan-detail', params: { nomor: pesanan.nomor } }"
            class="tombol tombol--sekunder tombol--penuh"
          >
            Lihat detail pesanan
          </RouterLink>
        </RingkasanPesanan>
      </div>
    </template>
  </div>
</template>

<style scoped>
.bayar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 380px;
  align-items: start;
  gap: 24px;
}

.bayar__utama {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-width: 0;
}

.bayar__status {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--navy);
  font-size: 1.375rem;
}

.bayar__data {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin: 0;
}

.bayar__data div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.bayar__data dt {
  color: var(--teks-redup);
  font-size: 0.8125rem;
}

.bayar__data dd {
  margin: 0;
  font-weight: 600;
  overflow-wrap: anywhere;
}

.bayar__nomor {
  font-variant-numeric: tabular-nums;
}

.bayar__total {
  color: var(--navy);
  font-size: 1.25rem;
  font-weight: 700;
}

.bayar__waktu {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 18px;
  border: 1px dashed var(--jingga);
  border-radius: var(--radius);
  background: var(--jingga-50);
}

.bayar__waktu-label {
  font-weight: 600;
}

.bayar__hitung {
  font-family: var(--font-judul);
  font-size: 1.75rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

.bayar__aksi {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.bayar__aksi .tombol {
  flex: 1 1 220px;
}

.bayar__aksi .tombol[aria-disabled='true'] {
  cursor: progress;
}

.berputar {
  animation: putar 1s linear infinite;
}

@keyframes putar {
  to {
    transform: rotate(360deg);
  }
}

.bayar__catatan {
  color: var(--teks-redup);
  font-size: 0.875rem;
}

.bayar__cara {
  padding-top: 20px;
  border-top: 1px solid var(--garis-lembut);
}

.bayar__subjudul {
  margin-bottom: 8px;
  font-size: 1rem;
}

.bayar__cara ol {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 0;
  padding-left: 20px;
  color: var(--teks);
  font-size: 0.9375rem;
}

.bayar__ringkasan {
  position: sticky;
  top: 16px;
}

.bayar__kirim {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 0.875rem;
}

.bayar__kirim span:first-child {
  color: var(--teks-redup);
}

.bayar__kirim span:last-child {
  text-align: right;
}

.kosong {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}

.kosong__judul {
  font-size: 1.25rem;
}

.kosong__teks {
  margin-bottom: 8px;
  color: var(--teks-redup);
}

@media (max-width: 959px) {
  .bayar {
    grid-template-columns: minmax(0, 1fr) 320px;
  }

  .bayar__data {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  }
}

@media (max-width: 719px) {
  .bayar {
    grid-template-columns: minmax(0, 1fr);
    gap: 16px;
  }

  .bayar__ringkasan {
    position: static;
  }

  .bayar__data {
    grid-template-columns: minmax(0, 1fr);
    gap: 8px;
  }

  .bayar__data div {
    flex-direction: row;
    flex-wrap: wrap;
    align-items: baseline;
    justify-content: space-between;
    gap: 4px 12px;
  }

  .bayar__data dt {
    font-size: 0.875rem;
  }

  .bayar__hitung {
    font-size: 1.5rem;
  }
}
</style>
