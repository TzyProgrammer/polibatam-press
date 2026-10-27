<script setup>
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { BookOpen, Check, Headphones, QrCode, RefreshCw } from '@lucide/vue'

import { api } from '../api/klien'
import KotakPesan from '../components/KotakPesan.vue'
import PilStatus from '../components/PilStatus.vue'
import SampulBuku from '../components/SampulBuku.vue'
import { KONTAK } from '../konfigurasi'
import { useNotifikasiStore } from '../stores/notifikasi'
import { usePesanStore } from '../stores/pesan'
import { formatRupiah, formatTanggalJam, labelMetodeBayar } from '../utils/format'

// Alur status pengiriman sama dengan Pesanan.pilihan_status_pengiriman() di backend.
const TAHAP_KIRIM = {
  delivery: [
    ['diproses', 'Diproses'],
    ['dikirim', 'Dikirim'],
    ['selesai', 'Selesai'],
  ],
  takeaway: [
    ['diproses', 'Diproses'],
    ['siap_diambil', 'Siap diambil'],
    ['selesai', 'Selesai'],
  ],
}

const PESAN_DITUTUP = {
  kedaluwarsa: 'Pesanan ini kedaluwarsa karena belum dibayar sampai batas waktu.',
  dibatalkan: 'Pesanan ini dibatalkan.',
  gagal: 'Pembayaran pesanan ini gagal.',
}

const kontak = [KONTAK.email && `email ${KONTAK.email}`, KONTAK.whatsapp && `WhatsApp ${KONTAK.whatsapp}`]
  .filter(Boolean)
  .join(' atau ')

const route = useRoute()
const notifikasi = useNotifikasiStore()
const pesan = usePesanStore()

const pesanan = ref(null)
const galat = ref('')
const tidakAda = ref(false)
const info = ref(null)
const memeriksa = ref(false)
const dimuatPada = ref(Date.now())

const nomor = computed(() => route.params.nomor)
const status = computed(() => pesanan.value?.status_pembayaran)
const lunas = computed(() => status.value === 'lunas')
const menunggu = computed(() => status.value === 'menunggu')
const bisaDibayar = computed(
  () => menunggu.value && Boolean(pesanan.value.pembayaran) && new Date(pesanan.value.batas_bayar) > dimuatPada.value,
)
const adaCetak = computed(() => (pesanan.value?.item || []).some((i) => i.format === 'cetak'))
const delivery = computed(() => pesanan.value?.metode_pengiriman === 'delivery')

const tahapKirim = computed(() => {
  const daftar = TAHAP_KIRIM[pesanan.value?.metode_pengiriman] || []
  const posisi = daftar.findIndex(([kode]) => kode === pesanan.value.status_pengiriman)
  return daftar.map(([kode, label], i) => ({
    kode,
    label,
    keadaan: i < posisi || (i === posisi && kode === 'selesai') ? 'selesai' : i === posisi ? 'aktif' : 'nanti',
    sekarang: i === posisi,
  }))
})

const meta = computed(() => {
  const p = pesanan.value
  const bagian = [`Dipesan ${formatTanggalJam(p.dibuat)}`]
  if (p.dibayar_pada) bagian.push(`Dibayar ${formatTanggalJam(p.dibayar_pada)}`)
  if (p.metode_pembayaran) bagian.push(labelMetodeBayar(p.metode_pembayaran))
  return bagian.join(' · ')
})

async function muat(n) {
  galat.value = ''
  tidakAda.value = false
  info.value = null
  try {
    const data = await api.get(`/pesanan/${encodeURIComponent(n)}/`)
    if (n !== nomor.value) return
    pesanan.value = data
    dimuatPada.value = Date.now()
    document.title = `Pesanan ${data.nomor} · Polibatam Press`
  } catch (e) {
    if (n !== nomor.value) return
    pesanan.value = null
    if (e.status === 404) tidakAda.value = true
    else if (e.status !== 401) galat.value = e.detail
  }
}

watch(
  nomor,
  (n) => {
    if (n && route.name === 'pesanan-detail') {
      pesanan.value = null
      muat(n)
    }
  },
  { immediate: true },
)

async function cekStatus() {
  if (memeriksa.value || !pesanan.value) return
  const n = pesanan.value.nomor
  memeriksa.value = true
  info.value = null
  try {
    const data = await api.post(`/pesanan/${encodeURIComponent(n)}/cek-status/`)
    if (n !== nomor.value) return
    pesanan.value = data
    dimuatPada.value = Date.now()
    if (data.status_pembayaran === 'lunas') {
      notifikasi.muat()
      pesan.tampilkan(`Pembayaran pesanan ${n} diterima.`, { jenis: 'sukses' })
    } else if (data.status_pembayaran === 'menunggu') {
      info.value = { jenis: 'info', teks: 'Pembayaran belum diterima Midtrans.' }
    }
  } catch (e) {
    if (e.status !== 401) info.value = { jenis: 'galat', teks: e.detail }
  } finally {
    memeriksa.value = false
  }
}

function keteranganItem(i) {
  if (i.format !== 'cetak') return i.format_label
  return `${i.format_label} × ${i.jumlah} · ${formatRupiah(i.harga_satuan)} per buku`
}
</script>

<template>
  <div class="wadah halaman">
    <nav class="jejak" aria-label="Jejak navigasi">
      <ol>
        <li><RouterLink :to="{ name: 'pesanan' }">Pesanan saya</RouterLink></li>
        <li aria-current="page">{{ nomor }}</li>
      </ol>
    </nav>

    <div v-if="tidakAda" class="kartu kartu--isi kosong">
      <h1 class="halaman__judul">Pesanan tidak ditemukan</h1>
      <p class="halaman__sub">Pesanan ini tidak ada atau bukan milik akun Anda.</p>
      <RouterLink :to="{ name: 'pesanan' }" class="tombol tombol--utama">Ke Pesanan saya</RouterLink>
    </div>

    <KotakPesan v-else-if="galat" jenis="galat">
      <span>{{ galat }}</span>
      <button type="button" class="tombol tombol--sekunder" @click="muat(nomor)">Coba lagi</button>
    </KotakPesan>

    <div v-else-if="!pesanan" aria-busy="true" aria-label="Memuat detail pesanan">
      <div class="kerangka" style="height: 40px; width: min(480px, 100%); margin-bottom: 24px" />
      <div class="pesanan">
        <div class="kerangka" style="height: 360px" />
        <div class="kerangka" style="height: 280px" />
      </div>
    </div>

    <template v-else>
      <div class="kepala-pesanan">
        <h1 class="halaman__judul">Pesanan {{ pesanan.nomor }}</h1>
        <div class="kepala-pesanan__status">
          <PilStatus
            jenis="pembayaran"
            :status="pesanan.status_pembayaran"
            :label="`Pembayaran: ${pesanan.status_pembayaran_label}`"
          />
          <PilStatus
            v-if="lunas && pesanan.pengiriman"
            jenis="pengiriman"
            :status="pesanan.status_pengiriman"
            :label="`Pengiriman: ${pesanan.status_pengiriman_label}`"
          />
        </div>
        <p class="kepala-pesanan__meta">{{ meta }}</p>
      </div>

      <KotakPesan v-if="menunggu" jenis="info" class="status-pesanan">
        <span v-if="bisaDibayar">Pesanan ini menunggu pembayaran sampai {{ formatTanggalJam(pesanan.batas_bayar) }}.</span>
        <span v-else>
          Batas waktu pembayaran sudah lewat. Pesanan yang tidak dibayar ditutup otomatis dalam beberapa menit.
        </span>
        <span class="status-pesanan__aksi">
          <RouterLink
            v-if="bisaDibayar"
            :to="{ name: 'pembayaran', params: { nomor: pesanan.nomor } }"
            class="tombol tombol--utama"
          >
            <QrCode :size="18" aria-hidden="true" />
            Bayar sekarang
          </RouterLink>
          <button
            type="button"
            class="tombol tombol--sekunder"
            :aria-disabled="memeriksa ? 'true' : undefined"
            @click="cekStatus"
          >
            <RefreshCw :size="18" aria-hidden="true" />
            {{ memeriksa ? 'Memeriksa…' : 'Cek status pembayaran' }}
          </button>
        </span>
      </KotakPesan>

      <KotakPesan v-else-if="!lunas" jenis="info" class="status-pesanan">
        <span>
          {{ PESAN_DITUTUP[pesanan.status_pembayaran] || `Status pembayaran: ${pesanan.status_pembayaran_label}.` }}
          <template v-if="adaCetak">Stok buku cetak sudah dikembalikan.</template>
          Silakan pesan ulang dari katalog.
        </span>
        <RouterLink :to="{ name: 'beranda' }">Lihat katalog</RouterLink>
      </KotakPesan>

      <KotakPesan v-if="info" :jenis="info.jenis" class="status-pesanan">{{ info.teks }}</KotakPesan>

      <div class="pesanan">
        <div class="pesanan__kiri">
          <section class="kartu kartu--isi" aria-labelledby="judul-isi">
            <h2 id="judul-isi" class="pesanan__subjudul">Isi pesanan</h2>
            <ul class="isi">
              <li v-for="i in pesanan.item" :key="`${i.produk_id}-${i.format}`" class="isi__baris">
                <RouterLink
                  v-if="i.buku"
                  :to="{ name: 'buku', params: { slug: i.buku.slug } }"
                  class="isi__sampul"
                  tabindex="-1"
                  aria-hidden="true"
                >
                  <SampulBuku :src="i.buku.sampul || ''" />
                </RouterLink>
                <div class="isi__teks">
                  <RouterLink v-if="i.buku" :to="{ name: 'buku', params: { slug: i.buku.slug } }" class="isi__judul">
                    {{ i.judul }}
                  </RouterLink>
                  <span v-else class="isi__judul">{{ i.judul }}</span>
                  <span class="isi__ket">{{ keteranganItem(i) }}</span>
                  <RouterLink
                    v-if="lunas && i.format !== 'cetak'"
                    :to="{
                      name: i.format === 'ebook' ? 'baca-ebook' : 'putar-audiobook',
                      params: { produkId: i.produk_id },
                    }"
                    class="isi__koleksi"
                  >
                    <component :is="i.format === 'ebook' ? BookOpen : Headphones" :size="16" aria-hidden="true" />
                    {{ i.format === 'ebook' ? 'Baca ebook' : 'Putar audiobook' }}
                  </RouterLink>
                </div>
                <span class="isi__harga">{{ formatRupiah(i.subtotal) }}</span>
              </li>
            </ul>
          </section>

          <section v-if="pesanan.pengiriman" class="kartu kartu--isi" aria-labelledby="judul-kirim">
            <h2 id="judul-kirim" class="pesanan__subjudul">Pengiriman</h2>
            <dl class="data">
              <div>
                <dt>Metode</dt>
                <dd>{{ pesanan.metode_pengiriman_label }}</dd>
              </div>
              <div>
                <dt>{{ delivery ? 'Penerima' : 'Pengambil' }}</dt>
                <dd>{{ pesanan.pengiriman.nama_penerima }} · {{ pesanan.pengiriman.no_telepon_penerima }}</dd>
              </div>
              <div v-if="pesanan.pengiriman.alamat">
                <dt>Alamat</dt>
                <dd>{{ pesanan.pengiriman.alamat }}</dd>
              </div>
              <div v-if="pesanan.pengiriman.lokasi_pengambilan">
                <dt>Lokasi pengambilan</dt>
                <dd>{{ pesanan.pengiriman.lokasi_pengambilan }}</dd>
              </div>
            </dl>

            <template v-if="lunas">
              <ol class="lini" aria-label="Status pengiriman">
                <li
                  v-for="t in tahapKirim"
                  :key="t.kode"
                  class="lini__item"
                  :class="`is-${t.keadaan}`"
                  :aria-current="t.sekarang ? 'step' : undefined"
                >
                  <span class="lini__tanda" aria-hidden="true">
                    <Check v-if="t.keadaan === 'selesai'" :size="14" :stroke-width="3" />
                  </span>
                  <span class="lini__label">{{ t.label }}</span>
                  <span v-if="t.keadaan === 'selesai'" class="sr-only">(selesai)</span>
                </li>
              </ol>
              <p v-if="pesanan.status_pengiriman === 'siap_diambil'" class="pesanan__catatan pesanan__catatan--penting">
                Pesanan siap diambil di {{ pesanan.pengiriman.lokasi_pengambilan }}.
              </p>
            </template>
            <p v-else-if="menunggu" class="pesanan__catatan">Pesanan diproses setelah pembayaran lunas.</p>
            <p v-else class="pesanan__catatan">Pesanan ini tidak dikirim karena pembayaran tidak selesai.</p>
          </section>
        </div>

        <aside class="kartu kartu--isi pesanan__bayar" aria-labelledby="judul-bayar">
          <h2 id="judul-bayar" class="pesanan__subjudul">Pembayaran</h2>
          <dl class="data data--sejajar">
            <div>
              <dt>Status</dt>
              <dd>{{ pesanan.status_pembayaran_label }}</dd>
            </div>
            <div>
              <dt>Metode</dt>
              <dd>{{ labelMetodeBayar(pesanan.metode_pembayaran) }}</dd>
            </div>
            <div v-if="menunggu">
              <dt>Batas bayar</dt>
              <dd>{{ formatTanggalJam(pesanan.batas_bayar) }}</dd>
            </div>
            <div v-if="pesanan.dibayar_pada">
              <dt>Dibayar</dt>
              <dd>{{ formatTanggalJam(pesanan.dibayar_pada) }}</dd>
            </div>
          </dl>
          <dl class="data data--sejajar biaya">
            <div>
              <dt>Subtotal</dt>
              <dd>{{ formatRupiah(pesanan.subtotal) }}</dd>
            </div>
            <div v-if="pesanan.metode_pengiriman !== 'tanpa'">
              <dt>Ongkir</dt>
              <dd>{{ pesanan.ongkir ? formatRupiah(pesanan.ongkir) : 'Gratis' }}</dd>
            </div>
            <div class="biaya__total">
              <dt>Total</dt>
              <dd>{{ formatRupiah(pesanan.total) }}</dd>
            </div>
          </dl>
          <p v-if="kontak" class="pesanan__catatan">
            Ada kendala dengan pesanan ini? Hubungi Polibatam Press melalui {{ kontak }}.
          </p>
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

.kepala-pesanan {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 20px;
}

.kepala-pesanan .halaman__judul {
  overflow-wrap: anywhere;
}

.kepala-pesanan__status {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.kepala-pesanan__meta {
  color: var(--teks-redup);
  font-size: 0.9375rem;
}

.status-pesanan {
  margin-bottom: 20px;
}

.status-pesanan__aksi {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.status-pesanan__aksi .tombol[aria-disabled='true'] {
  cursor: progress;
}

.pesanan {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  align-items: start;
  gap: 24px;
}

.pesanan__kiri {
  display: flex;
  flex-direction: column;
  gap: 24px;
  min-width: 0;
}

.pesanan__subjudul {
  margin-bottom: 16px;
  font-size: 1.125rem;
}

.pesanan__bayar {
  position: sticky;
  top: 16px;
}

.pesanan__catatan {
  margin-top: 16px;
  color: var(--teks-redup);
  font-size: 0.875rem;
}

.pesanan__catatan--penting {
  padding: 10px 12px;
  border-radius: var(--radius-kecil);
  background: var(--sukses-50);
  color: var(--sukses);
  font-weight: 600;
}

/* Isi pesanan */
.isi {
  display: flex;
  flex-direction: column;
  margin: 0;
  padding: 0;
  list-style: none;
}

.isi__baris {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding-block: 14px;
  border-top: 1px solid var(--garis-lembut);
}

.isi__baris:first-child {
  padding-top: 0;
  border-top: 0;
}

.isi__baris:last-child {
  padding-bottom: 0;
}

.isi__sampul {
  flex: none;
  width: 56px;
  overflow: hidden;
  border: 1px solid var(--garis-lembut);
  border-radius: 6px;
}

.isi__teks {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  min-width: 0;
}

.isi__judul {
  color: var(--teks);
  font-weight: 600;
  line-height: 1.4;
  text-decoration: none;
  overflow-wrap: anywhere;
}

a.isi__judul:hover {
  color: var(--navy);
  text-decoration: underline;
}

.isi__ket {
  color: var(--teks-redup);
  font-size: 0.875rem;
}

.isi__koleksi {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 36px;
  font-size: 0.875rem;
  font-weight: 700;
}

.isi__harga {
  flex: none;
  font-weight: 700;
}

/* Data (dl) */
.data {
  display: flex;
  flex-direction: column;
  gap: 10px;
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

.data--sejajar div {
  display: flex;
  justify-content: space-between;
}

.data--sejajar dd {
  text-align: right;
}

.biaya {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--garis-lembut);
}

.biaya__total {
  padding-top: 10px;
  border-top: 1px solid var(--garis-lembut);
  font-weight: 700;
}

.biaya__total dt {
  color: var(--teks);
}

.biaya__total dd {
  color: var(--navy);
  font-size: 1.25rem;
}

/* Lini status pengiriman */
.lini {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin: 20px 0 0;
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
.lini__item.is-aktif::before {
  background: var(--isi-utama);
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
  background: var(--isi-utama);
  color: #fff;
}

.is-aktif .lini__tanda {
  border-color: var(--navy);
  box-shadow: inset 0 0 0 4px var(--permukaan);
  background: var(--isi-utama);
}

.is-selesai,
.is-aktif {
  color: var(--navy);
}

.kosong {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
}

@media (max-width: 959px) {
  .pesanan {
    grid-template-columns: minmax(0, 1fr) 300px;
  }
}

@media (max-width: 719px) {
  .pesanan {
    grid-template-columns: minmax(0, 1fr);
    gap: 16px;
  }

  .pesanan__kiri {
    gap: 16px;
  }

  .pesanan__bayar {
    position: static;
  }

  .data div {
    grid-template-columns: minmax(0, 1fr);
    gap: 0;
  }

  .data--sejajar div {
    gap: 12px;
  }
}
</style>
