<script setup>
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { BookOpen, FileText, Headphones, Minus, Plus, ShoppingCart } from '@lucide/vue'

import { api } from '../api/klien'
import KotakPesan from '../components/KotakPesan.vue'
import SampulBuku from '../components/SampulBuku.vue'
import { useAuthStore } from '../stores/auth'
import { useKeranjangStore } from '../stores/keranjang'
import { usePesanStore } from '../stores/pesan'
import { formatRupiah } from '../utils/format'

const IKON = { cetak: BookOpen, ebook: FileText, audiobook: Headphones }
const KETERANGAN = {
  cetak: (p) => `Stok tersedia: ${p.stok} · dikirim di Kota Batam atau diambil di kampus`,
  ebook: () => 'Dibaca di aplikasi · diberi watermark identitas pembeli',
  audiobook: () => 'Diputar di aplikasi lewat streaming terenkripsi',
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const keranjang = useKeranjangStore()
const pesan = usePesanStore()

const buku = ref(null)
const memuat = ref(true)
const galat = ref('')
const tidakAda = ref(false)
const pilihan = ref(null)
const jumlah = ref(1)
const menambah = ref(false)
const galatTambah = ref('')

async function muat() {
  if (route.name !== 'buku') return
  memuat.value = true
  galat.value = ''
  tidakAda.value = false
  try {
    const data = await api.get(`/katalog/buku/${encodeURIComponent(route.params.slug)}/`)
    buku.value = data
    pilihan.value = data.produk.find((p) => p.tersedia)?.id ?? null
    document.title = `${data.judul} · Polibatam Press`
  } catch (e) {
    buku.value = null
    if (e.status === 404) {
      tidakAda.value = true
      document.title = 'Buku tidak ditemukan · Polibatam Press'
    } else {
      galat.value = e.detail
    }
  } finally {
    memuat.value = false
  }
}

watch(() => route.params.slug, muat, { immediate: true })

const produk = computed(() => buku.value?.produk.find((p) => p.id === pilihan.value) || null)
const cetak = computed(() => produk.value?.format === 'cetak')
const maksJumlah = computed(() => (cetak.value ? Math.max(1, produk.value.stok || 1) : 1))

watch(pilihan, () => {
  jumlah.value = 1
  galatTambah.value = ''
})

function keterangan(p) {
  return p.tersedia ? KETERANGAN[p.format]?.(p) : `${p.keterangan} · belum bisa dibeli`
}

function aturJumlah(nilai) {
  const angka = Number.parseInt(nilai, 10)
  jumlah.value = Math.min(maksJumlah.value, Math.max(1, Number.isNaN(angka) ? 1 : angka))
}

const info = computed(() => {
  const b = buku.value
  if (!b) return []
  return [
    ['ISBN', b.isbn],
    ['Tahun terbit', b.tahun_terbit],
    ['Jumlah halaman', b.jumlah_halaman && `${b.jumlah_halaman} halaman`],
    ['Ukuran', b.ukuran],
    ['Kategori', b.kategori?.nama],
  ].filter(([, nilai]) => nilai)
})

async function tambah() {
  if (!produk.value) return
  if (!auth.sudahMasuk) {
    router.push({ name: 'masuk', query: { next: route.fullPath } })
    return
  }
  menambah.value = true
  galatTambah.value = ''
  try {
    await keranjang.tambah(produk.value.id, cetak.value ? jumlah.value : 1)
    pesan.tampilkan(`${buku.value.judul} (${produk.value.format_label}) masuk ke keranjang.`, {
      jenis: 'sukses',
      tautan: { to: { name: 'keranjang' }, label: 'Lihat keranjang' },
    })
  } catch (e) {
    if (e.status !== 401) galatTambah.value = e.detail
  } finally {
    menambah.value = false
  }
}
</script>

<template>
  <div class="wadah halaman">
    <div v-if="memuat && !buku" class="detail" aria-busy="true" aria-label="Memuat detail buku">
      <div class="kerangka detail__sampul" />
      <div class="detail__info">
        <div class="kerangka" style="height: 36px; width: 70%" />
        <div class="kerangka" style="height: 18px; width: 40%" />
        <div class="kerangka" style="height: 220px" />
      </div>
    </div>

    <div v-else-if="tidakAda" class="kartu kartu--isi kosong">
      <h1 class="halaman__judul">Buku tidak ditemukan</h1>
      <p class="halaman__sub">Buku ini tidak ada atau sudah tidak dijual.</p>
      <RouterLink :to="{ name: 'beranda' }" class="tombol tombol--utama">Kembali ke katalog</RouterLink>
    </div>

    <KotakPesan v-else-if="galat" jenis="galat">
      <span>{{ galat }}</span>
      <button type="button" class="tombol tombol--sekunder" @click="muat">Coba lagi</button>
    </KotakPesan>

    <template v-else-if="buku">
      <nav class="jejak" aria-label="Jejak navigasi">
        <ol>
          <li><RouterLink :to="{ name: 'beranda' }">Katalog</RouterLink></li>
          <li v-if="buku.kategori">
            <RouterLink :to="{ name: 'beranda', query: { kategori: buku.kategori.slug } }">{{ buku.kategori.nama }}</RouterLink>
          </li>
          <li aria-current="page">{{ buku.judul }}</li>
        </ol>
      </nav>

      <div class="detail">
        <SampulBuku class="detail__sampul" :src="buku.sampul" :alt="`Sampul buku ${buku.judul}`" :judul="buku.judul" segera />

        <div class="detail__info">
          <div class="detail__kepala">
            <h1 class="detail__judul">{{ buku.judul }}</h1>
            <p class="detail__penulis">oleh {{ buku.penulis }}</p>
            <span v-if="buku.kategori" class="detail__kategori">{{ buku.kategori.nama }}</span>
          </div>

          <fieldset class="format">
            <legend class="format__judul">Pilih format</legend>
            <label
              v-for="p in buku.produk"
              :key="p.id"
              class="format__pilihan"
              :class="{ 'is-dipilih': pilihan === p.id, 'is-nonaktif': !p.tersedia }"
            >
              <input v-model="pilihan" type="radio" name="format" :value="p.id" :disabled="!p.tersedia">
              <component :is="IKON[p.format]" :size="24" class="format__ikon" />
              <span class="format__teks">
                <span class="format__nama">{{ p.format_label }}</span>
                <span class="format__ket">{{ keterangan(p) }}</span>
              </span>
              <span class="format__harga">{{ formatRupiah(p.harga) }}</span>
            </label>
          </fieldset>

          <div v-if="cetak" class="jumlah">
            <span id="label-jumlah" class="jumlah__label">Jumlah</span>
            <div class="penghitung" role="group" aria-labelledby="label-jumlah">
              <button type="button" aria-label="Kurangi jumlah" :disabled="jumlah <= 1" @click="aturJumlah(jumlah - 1)">
                <Minus :size="18" />
              </button>
              <input
                :value="jumlah"
                type="number"
                min="1"
                :max="maksJumlah"
                inputmode="numeric"
                aria-label="Jumlah buku cetak"
                @change="aturJumlah($event.target.value)"
              >
              <button type="button" aria-label="Tambah jumlah" :disabled="jumlah >= maksJumlah" @click="aturJumlah(jumlah + 1)">
                <Plus :size="18" />
              </button>
            </div>
            <span class="jumlah__ket">Maksimal {{ maksJumlah }} buku</span>
          </div>

          <KotakPesan v-if="galatTambah" jenis="galat">{{ galatTambah }}</KotakPesan>

          <div>
            <button
              type="button"
              class="tombol tombol--utama tombol--besar"
              :disabled="!produk || menambah"
              @click="tambah"
            >
              <ShoppingCart :size="20" />
              {{ menambah ? 'Menambahkan…' : 'Tambah ke keranjang' }}
            </button>
          </div>

          <p v-if="!produk" class="detail__catatan">Belum ada format yang bisa dibeli saat ini.</p>
          <p class="detail__catatan">
            Ebook dan audiobook masuk ke Koleksi setelah pembayaran lunas. Buku cetak dikirim atau diambil sesuai pilihan saat
            checkout.
          </p>
        </div>
      </div>

      <div class="detail__bawah">
        <section class="kartu kartu--isi detail__sinopsis" aria-labelledby="judul-sinopsis">
          <h2 id="judul-sinopsis" class="detail__subjudul">Sinopsis</h2>
          <p class="detail__sinopsis-teks">{{ buku.sinopsis || 'Sinopsis belum tersedia.' }}</p>
        </section>
        <section v-if="info.length" class="kartu kartu--isi detail__informasi" aria-labelledby="judul-info">
          <h2 id="judul-info" class="detail__subjudul">Informasi buku</h2>
          <dl class="info">
            <template v-for="[label, nilai] in info" :key="label">
              <dt>{{ label }}</dt>
              <dd>{{ nilai }}</dd>
            </template>
          </dl>
        </section>
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
  margin: 0 0 16px;
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

.detail {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 32px 48px;
}

.detail__sampul {
  flex: 0 1 360px;
  overflow: hidden;
  border: 1px solid var(--garis);
  border-radius: var(--radius);
  aspect-ratio: 3 / 4;
}

.detail__info {
  display: flex;
  flex: 1 1 480px;
  flex-direction: column;
  gap: 20px;
  min-width: 0;
}

.detail__kepala {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.detail__judul {
  font-size: 2rem;
}

.detail__penulis {
  color: var(--teks-redup);
  font-size: 1rem;
}

.detail__kategori {
  align-self: flex-start;
  margin-top: 4px;
  padding: 4px 12px;
  border-radius: 999px;
  background: var(--biru-50);
  color: var(--navy);
  font-size: 0.8125rem;
  font-weight: 600;
}

.format {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 0;
  padding: 0;
  border: 0;
}

.format__judul {
  margin-bottom: 10px;
  padding: 0;
  font-weight: 600;
}

.format__pilihan {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  border: 1px solid var(--garis);
  border-radius: var(--radius);
  background: var(--permukaan);
  cursor: pointer;
}

.format__pilihan:hover {
  border-color: var(--navy);
}

.format__pilihan.is-dipilih {
  border-color: var(--navy);
  box-shadow: inset 0 0 0 1px var(--navy);
  background: var(--navy-50);
}

.format__pilihan.is-nonaktif {
  border-style: dashed;
  background: #f3f4f7;
  color: var(--teks-redup);
  cursor: not-allowed;
}

.format__pilihan input {
  flex: none;
  width: 20px;
  height: 20px;
  margin: 0;
  accent-color: var(--navy);
}

.format__pilihan:has(input:focus-visible) {
  outline: 3px solid var(--navy);
  outline-offset: 2px;
}

.format__ikon {
  flex: none;
  color: var(--navy);
}

.is-nonaktif .format__ikon {
  color: var(--teks-redup);
}

.format__teks {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.format__nama {
  font-weight: 600;
}

.format__ket {
  color: var(--teks-redup);
  font-size: 0.8125rem;
}

.format__harga {
  flex: none;
  color: var(--navy);
  font-size: 1rem;
  font-weight: 700;
}

.is-nonaktif .format__harga {
  color: var(--teks-redup);
}

.jumlah {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 16px;
}

.jumlah__label {
  font-weight: 600;
}

.jumlah__ket {
  color: var(--teks-redup);
  font-size: 0.8125rem;
}

.penghitung {
  display: flex;
  align-items: center;
  overflow: hidden;
  border: 1px solid var(--garis-isian);
  border-radius: var(--radius-kecil);
  background: var(--permukaan);
}

.penghitung button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border: 0;
  background: transparent;
  color: var(--navy);
  cursor: pointer;
}

.penghitung button:disabled {
  color: var(--garis-isian);
  cursor: not-allowed;
}

.penghitung input {
  width: 56px;
  height: 44px;
  border: 0;
  border-inline: 1px solid var(--garis);
  text-align: center;
  -moz-appearance: textfield;
}

.penghitung input::-webkit-inner-spin-button,
.penghitung input::-webkit-outer-spin-button {
  margin: 0;
  -webkit-appearance: none;
}

.detail__catatan {
  max-width: 560px;
  color: var(--teks-redup);
  font-size: 0.875rem;
}

.detail__bawah {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 24px;
  margin-top: 32px;
}

.detail__sinopsis {
  flex: 2 1 560px;
  min-width: 0;
}

.detail__informasi {
  flex: 1 1 320px;
  min-width: 0;
}

.detail__subjudul {
  margin-bottom: 12px;
  font-size: 1.25rem;
}

.detail__sinopsis-teks {
  color: var(--teks);
  white-space: pre-line;
}

.info {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 8px 16px;
  margin: 0;
}

.info dt {
  color: var(--teks-redup);
}

.info dd {
  margin: 0;
  overflow-wrap: anywhere;
}

.kosong {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
}

@media (max-width: 719px) {
  .detail__sampul {
    flex-basis: 100%;
    max-width: 240px;
    margin-inline: auto;
  }

  .detail__judul {
    font-size: 1.5rem;
  }
}
</style>
