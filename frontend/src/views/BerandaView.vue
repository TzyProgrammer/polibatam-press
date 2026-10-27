<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { api } from '../api/klien'
import KartuBuku from '../components/KartuBuku.vue'
import KotakPesan from '../components/KotakPesan.vue'
import NavigasiHalaman from '../components/NavigasiHalaman.vue'

// Filter katalog disimpan di URL (?q=&kategori=&tipe=&urutan=&halaman=) agar bisa dibagikan dan
// tombol Kembali di peramban bekerja. Nilainya diteruskan ke API /api/katalog/buku/.
const UKURAN = 12
const TIPE = [
  { nilai: '', label: 'Semua' },
  { nilai: 'cetak', label: 'Buku cetak' },
  { nilai: 'ebook', label: 'Ebook' },
  { nilai: 'audiobook', label: 'Audiobook' },
]
const URUTAN = [
  { nilai: '', label: 'Terbaru' },
  { nilai: 'judul', label: 'Judul (A–Z)' },
  { nilai: 'harga', label: 'Harga terendah' },
  { nilai: '-harga', label: 'Harga tertinggi' },
]

const route = useRoute()
const router = useRouter()

const kategori = ref([])
const hasil = ref(null)
const memuat = ref(false)
const galat = ref('')
const judulKatalog = ref(null)

function teks(nilai) {
  return typeof nilai === 'string' ? nilai : ''
}

const filter = computed(() => ({
  q: teks(route.query.q).trim(),
  kategori: teks(route.query.kategori),
  tipe: teks(route.query.tipe),
  urutan: teks(route.query.urutan),
  halaman: Math.max(1, Number.parseInt(teks(route.query.halaman), 10) || 1),
}))

// Banner hanya di tampilan awal; saat mencari atau menyaring, hasil langsung tampil di atas.
const sedangMenyaring = computed(
  () => Boolean(filter.value.q || filter.value.kategori || filter.value.tipe) || filter.value.halaman > 1,
)

function kueri(perubahan) {
  const baru = { ...route.query, ...perubahan }
  if (!('halaman' in perubahan)) delete baru.halaman
  for (const kunci of Object.keys(baru)) {
    if (baru[kunci] === '' || baru[kunci] === undefined || baru[kunci] === null) delete baru[kunci]
  }
  return baru
}

function ubah(perubahan) {
  router.push({ name: 'beranda', query: kueri(perubahan) })
}

function tautanHalaman(n) {
  return { name: 'beranda', query: kueri({ halaman: n > 1 ? String(n) : undefined }) }
}

let nomorPermintaan = 0

async function muat() {
  if (route.name !== 'beranda') return
  const nomor = ++nomorPermintaan
  const f = filter.value
  memuat.value = true
  galat.value = ''
  try {
    const data = await api.get('/katalog/buku/', {
      q: f.q,
      kategori: f.kategori,
      tipe: f.tipe,
      urutan: f.urutan,
      page: f.halaman > 1 ? f.halaman : undefined,
      ukuran: UKURAN,
    })
    if (nomor === nomorPermintaan) hasil.value = data
  } catch (e) {
    if (nomor !== nomorPermintaan) return
    if (e.status === 404 && f.halaman > 1) {
      router.replace(tautanHalaman(1))
      return
    }
    galat.value = e.detail
  } finally {
    if (nomor === nomorPermintaan) memuat.value = false
  }
}

watch(
  [() => filter.value.q, () => filter.value.kategori, () => filter.value.tipe, () => filter.value.urutan, () => filter.value.halaman],
  (baru, lama) => {
    muat()
    if (lama && baru[4] !== lama[4]) document.getElementById('katalog')?.scrollIntoView({ block: 'start' })
  },
  { immediate: true },
)

api
  .get('/katalog/kategori/')
  .then((data) => {
    kategori.value = data
  })
  .catch(() => {})

const jumlahHalaman = computed(() => (hasil.value ? Math.max(1, Math.ceil(hasil.value.count / UKURAN)) : 1))

const infoHasil = computed(() => {
  if (!hasil.value?.count) return ''
  const awal = (filter.value.halaman - 1) * UKURAN + 1
  const akhir = awal + hasil.value.results.length - 1
  return `Menampilkan ${awal}–${akhir} dari ${hasil.value.count} buku`
})

async function keKatalog() {
  document.getElementById('katalog')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  await nextTick()
  judulKatalog.value?.focus({ preventScroll: true })
}
</script>

<template>
  <div>
    <section v-if="!sedangMenyaring" class="hero" aria-labelledby="judul-hero">
      <div class="wadah">
        <div class="hero__kotak">
          <div class="hero__teks">
            <p class="hero__kicker">Penerbit Politeknik Negeri Batam</p>
            <h1 id="judul-hero" class="hero__judul">Buku terbitan Polibatam Press</h1>
            <p class="hero__deskripsi">
              Beli buku cetak, ebook, dan audiobook. Ebook dibaca dan audiobook diputar langsung dari Koleksi Anda.
            </p>
            <div class="hero__aksi">
              <button type="button" class="tombol tombol--besar hero__tombol-utama" @click="keKatalog">Lihat katalog</button>
              <RouterLink :to="{ name: 'isbn' }" class="tombol tombol--besar hero__tombol-garis">Ajukan ISBN naskah</RouterLink>
            </div>
          </div>
          <div class="hero__hiasan" aria-hidden="true">
            <span class="hero__buku hero__buku--1" />
            <span class="hero__buku hero__buku--2" />
            <span class="hero__buku hero__buku--3" />
            <span class="hero__alas" />
          </div>
        </div>
      </div>
    </section>

    <section id="katalog" class="wadah katalog" aria-labelledby="judul-katalog">
      <div class="katalog__kepala">
        <div>
          <component :is="sedangMenyaring ? 'h1' : 'h2'" id="judul-katalog" ref="judulKatalog" class="katalog__judul" tabindex="-1">
            {{ filter.q ? 'Hasil pencarian' : 'Katalog' }}
          </component>
          <p class="katalog__info">{{ infoHasil }}</p>
        </div>
        <div class="katalog__saring">
          <div class="isian">
            <label for="saring-kategori" class="isian__label">Kategori</label>
            <select
              id="saring-kategori"
              class="isian__kontrol"
              :value="filter.kategori"
              @change="ubah({ kategori: $event.target.value })"
            >
              <option value="">Semua kategori</option>
              <option v-for="k in kategori" :key="k.slug" :value="k.slug">{{ k.nama }} ({{ k.jumlah_buku }})</option>
            </select>
          </div>
          <div class="isian">
            <label for="saring-urutan" class="isian__label">Urutkan</label>
            <select id="saring-urutan" class="isian__kontrol" :value="filter.urutan" @change="ubah({ urutan: $event.target.value })">
              <option v-for="u in URUTAN" :key="u.nilai" :value="u.nilai">{{ u.label }}</option>
            </select>
          </div>
        </div>
      </div>

      <KotakPesan v-if="filter.q" jenis="info">
        <span>Hasil untuk “{{ filter.q }}”.</span>
        <RouterLink :to="{ name: 'beranda', query: kueri({ q: undefined }) }">Hapus pencarian</RouterLink>
      </KotakPesan>

      <div class="katalog__tipe" role="group" aria-label="Tipe produk">
        <button
          v-for="t in TIPE"
          :key="t.nilai"
          type="button"
          class="pil"
          :aria-pressed="filter.tipe === t.nilai ? 'true' : 'false'"
          @click="ubah({ tipe: t.nilai })"
        >
          {{ t.label }}
        </button>
      </div>

      <KotakPesan v-if="galat" jenis="galat">
        <span>{{ galat }}</span>
        <button type="button" class="tombol tombol--sekunder" @click="muat">Coba lagi</button>
      </KotakPesan>

      <div v-else-if="!hasil" class="grid-buku" aria-busy="true" aria-label="Memuat katalog">
        <div v-for="n in 12" :key="n" class="kerangka-kartu">
          <div class="kerangka kerangka-kartu__sampul" />
          <div class="kerangka kerangka-kartu__baris" />
          <div class="kerangka kerangka-kartu__baris kerangka-kartu__baris--pendek" />
        </div>
      </div>

      <template v-else>
        <div v-if="hasil.results.length" class="grid-buku" :aria-busy="memuat ? 'true' : 'false'">
          <KartuBuku v-for="b in hasil.results" :key="b.id" :buku="b" />
        </div>
        <div v-else class="kartu kartu--isi katalog__kosong">
          <h3>Buku tidak ditemukan</h3>
          <p>Coba kata kunci lain atau hapus filter yang dipilih.</p>
          <RouterLink v-if="sedangMenyaring" :to="{ name: 'beranda' }" class="tombol tombol--sekunder">Hapus semua filter</RouterLink>
        </div>
        <NavigasiHalaman :halaman="filter.halaman" :jumlah="jumlahHalaman" :tautan="tautanHalaman" label="Halaman katalog" />
      </template>
    </section>
  </div>
</template>

<style scoped>
.hero {
  padding-top: 32px;
}

.hero__kotak {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 32px;
  overflow: hidden;
  padding: 40px 48px;
  border-radius: 16px;
  background: var(--latar-merek);
  color: #fff;
}

.hero__teks {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 600px;
}

.hero__kicker {
  color: var(--biru);
  font-size: 0.875rem;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.hero__judul {
  color: #fff;
  font-size: 2.25rem;
}

.hero__deskripsi {
  color: #e6ebf5;
  font-size: 1.0625rem;
}

.hero__aksi {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 8px;
}

.hero__tombol-utama {
  background: #fff;
  color: #1e376c;
}

.hero__tombol-utama:hover {
  background: #e8f7fc;
  color: #14264d;
}

.hero__tombol-garis {
  border-color: #fff;
  background: transparent;
  color: #fff;
}

.hero__tombol-garis:hover {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
}

.hero__tombol-utama:focus-visible,
.hero__tombol-garis:focus-visible {
  outline-color: #fff;
}

.hero__hiasan {
  position: relative;
  flex: none;
  width: 260px;
  height: 190px;
}

.hero__buku {
  position: absolute;
  bottom: 14px;
  width: 54px;
  border-radius: 6px 6px 3px 3px;
}

.hero__buku::before {
  content: '';
  position: absolute;
  top: 18px;
  left: 10px;
  right: 10px;
  height: 4px;
  border-radius: 2px;
  background: rgba(30, 55, 108, 0.35);
}

.hero__buku--1 {
  left: 36px;
  height: 150px;
  background: var(--biru);
}

.hero__buku--2 {
  left: 98px;
  height: 126px;
  background: #fff;
}

.hero__buku--3 {
  left: 158px;
  height: 140px;
  background: var(--jingga);
  transform: rotate(14deg);
  transform-origin: bottom left;
}

.hero__alas {
  position: absolute;
  right: 16px;
  bottom: 6px;
  left: 16px;
  height: 8px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.28);
}

.katalog {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-block: 32px 48px;
}

.katalog__kepala {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
}

.katalog__judul {
  font-size: 1.5rem;
}

.katalog__judul:focus {
  outline: none;
}

.katalog__info {
  min-height: 1.5em;
  margin-top: 4px;
  color: var(--teks-redup);
  font-size: 0.875rem;
}

.katalog__saring {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.katalog__saring .isian {
  min-width: 190px;
}

.katalog__tipe {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.grid-buku {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 20px;
}

.grid-buku[aria-busy='true'] {
  opacity: 0.6;
}

.kerangka-kartu {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.kerangka-kartu__sampul {
  aspect-ratio: 3 / 4;
}

.kerangka-kartu__baris {
  height: 14px;
}

.kerangka-kartu__baris--pendek {
  width: 60%;
}

.katalog__kosong {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}

@media (max-width: 719px) {
  .hero {
    padding-top: 16px;
  }

  .hero__kotak {
    padding: 24px;
  }

  .hero__judul {
    font-size: 1.625rem;
  }

  .hero__hiasan {
    display: none;
  }

  .katalog {
    padding-block: 24px 40px;
  }

  .katalog__saring {
    width: 100%;
  }

  .katalog__saring .isian {
    flex: 1 1 140px;
    min-width: 0;
  }

  .katalog__tipe {
    flex-wrap: nowrap;
    overflow-x: auto;
  }

  .katalog__tipe .pil {
    flex: none;
  }

  .grid-buku {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
  }
}
</style>
