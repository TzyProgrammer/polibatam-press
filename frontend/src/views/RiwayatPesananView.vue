<script setup>
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ReceiptText } from '@lucide/vue'

import { api } from '../api/klien'
import KotakPesan from '../components/KotakPesan.vue'
import NavigasiHalaman from '../components/NavigasiHalaman.vue'
import PilStatus from '../components/PilStatus.vue'
import { formatRupiah, formatTanggal, labelPengirimanSingkat } from '../utils/format'

// 10 pesanan per halaman (HalamanPesanan di backend); halaman disimpan di URL (?halaman=).
const UKURAN = 10

const route = useRoute()
const router = useRouter()

const hasil = ref(null)
const memuat = ref(false)
const galat = ref('')

const halaman = computed(() => {
  const nilai = typeof route.query.halaman === 'string' ? route.query.halaman : ''
  return Math.max(1, Number.parseInt(nilai, 10) || 1)
})
const jumlahHalaman = computed(() => (hasil.value ? Math.max(1, Math.ceil(hasil.value.count / UKURAN)) : 1))
const daftar = computed(() => hasil.value?.results || [])

function tautanHalaman(n) {
  return { name: 'pesanan', query: n > 1 ? { halaman: String(n) } : {} }
}

let nomorPermintaan = 0

async function muat() {
  if (route.name !== 'pesanan') return
  const nomor = ++nomorPermintaan
  const h = halaman.value
  memuat.value = true
  galat.value = ''
  try {
    const data = await api.get('/pesanan/', { page: h > 1 ? h : undefined })
    if (nomor === nomorPermintaan) hasil.value = data
  } catch (e) {
    if (nomor !== nomorPermintaan) return
    if (e.status === 404 && h > 1) {
      router.replace(tautanHalaman(1))
      return
    }
    if (e.status !== 401) galat.value = e.detail
  } finally {
    if (nomor === nomorPermintaan) memuat.value = false
  }
}

watch(halaman, muat, { immediate: true })

// Tombol Bayar hanya untuk pesanan yang masih menunggu dan belum lewat batas bayar.
function bisaDibayar(p) {
  return p.status_pembayaran === 'menunggu' && p.batas_bayar && new Date(p.batas_bayar) > Date.now()
}

function statusKirim(p) {
  if (p.metode_pengiriman === 'tanpa') return 'Tidak ada'
  return p.status_pengiriman_label
}

// Baris pengiriman di kartu ponsel (tanpa judul kolom "Pengiriman" seperti di tabel).
function ringkasKirim(p) {
  if (p.metode_pengiriman === 'tanpa') return 'Produk digital, tanpa pengiriman'
  return `${labelPengirimanSingkat(p.metode_pengiriman)}: ${statusKirim(p)}`
}

function isiPesanan(p) {
  return `${p.ringkasan} · ${p.jumlah_item} item`
}
</script>

<template>
  <div class="wadah halaman">
    <div class="halaman__kepala">
      <h1 class="halaman__judul">Pesanan saya</h1>
      <p class="halaman__sub">Pesanan terbaru tampil paling atas.</p>
    </div>

    <KotakPesan v-if="galat" jenis="galat">
      <span>{{ galat }}</span>
      <button type="button" class="tombol tombol--sekunder" @click="muat">Coba lagi</button>
    </KotakPesan>

    <div v-else-if="!hasil" class="kartu kartu--isi" aria-busy="true" aria-label="Memuat pesanan">
      <div v-for="n in 4" :key="n" class="kerangka" style="height: 48px; margin-bottom: 12px" />
    </div>

    <div v-else-if="!hasil.count" class="kartu kartu--isi kosong">
      <ReceiptText :size="40" class="kosong__ikon" aria-hidden="true" />
      <h2 class="kosong__judul">Belum ada pesanan</h2>
      <p class="kosong__teks">Pesanan yang Anda buat saat checkout akan tampil di sini.</p>
      <RouterLink :to="{ name: 'beranda' }" class="tombol tombol--utama">Lihat katalog</RouterLink>
    </div>

    <template v-else>
      <!-- Desktop: tabel -->
      <div class="kartu tabel-wadah" :aria-busy="memuat ? 'true' : undefined">
        <table class="tabel">
          <caption class="sr-only">
            Daftar pesanan, halaman {{ halaman }} dari {{ jumlahHalaman }}
          </caption>
          <thead>
            <tr>
              <th scope="col">Nomor pesanan</th>
              <th scope="col">Tanggal</th>
              <th scope="col">Isi pesanan</th>
              <th scope="col" class="tabel__angka">Total</th>
              <th scope="col">Pembayaran</th>
              <th scope="col">Pengiriman</th>
              <th scope="col"><span class="sr-only">Aksi</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in daftar" :key="p.nomor">
              <td>
                <RouterLink :to="{ name: 'pesanan-detail', params: { nomor: p.nomor } }" class="tabel__nomor">
                  {{ p.nomor }}
                </RouterLink>
              </td>
              <td class="tabel__redup">{{ formatTanggal(p.dibuat) }}</td>
              <td class="tabel__isi">{{ isiPesanan(p) }}</td>
              <td class="tabel__angka">{{ formatRupiah(p.total) }}</td>
              <td><PilStatus jenis="pembayaran" :status="p.status_pembayaran" :label="p.status_pembayaran_label" /></td>
              <td>
                <span class="tabel__kirim">{{ statusKirim(p) }}</span>
                <span class="tabel__redup tabel__kecil">{{ labelPengirimanSingkat(p.metode_pengiriman) }}</span>
              </td>
              <td class="tabel__aksi">
                <RouterLink
                  v-if="bisaDibayar(p)"
                  :to="{ name: 'pembayaran', params: { nomor: p.nomor } }"
                  class="tombol tombol--utama tombol--kecil"
                  :aria-label="`Bayar pesanan ${p.nomor}`"
                >
                  Bayar
                </RouterLink>
                <RouterLink
                  v-else
                  :to="{ name: 'pesanan-detail', params: { nomor: p.nomor } }"
                  class="tombol tombol--sekunder tombol--kecil"
                  :aria-label="`Detail pesanan ${p.nomor}`"
                >
                  Detail
                </RouterLink>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Ponsel: kartu -->
      <ul class="kartu-pesanan" :aria-busy="memuat ? 'true' : undefined">
        <li v-for="p in daftar" :key="p.nomor" class="kartu kartu-pesanan__item">
          <div class="kartu-pesanan__atas">
            <RouterLink :to="{ name: 'pesanan-detail', params: { nomor: p.nomor } }" class="kartu-pesanan__nomor">
              {{ p.nomor }}
            </RouterLink>
            <span class="tabel__redup tabel__kecil">{{ formatTanggal(p.dibuat) }}</span>
          </div>
          <p class="kartu-pesanan__isi">{{ isiPesanan(p) }}</p>
          <div class="kartu-pesanan__status">
            <PilStatus jenis="pembayaran" :status="p.status_pembayaran" :label="p.status_pembayaran_label" />
            <span class="tabel__redup tabel__kecil">{{ ringkasKirim(p) }}</span>
          </div>
          <div class="kartu-pesanan__bawah">
            <span class="kartu-pesanan__total">{{ formatRupiah(p.total) }}</span>
            <RouterLink
              v-if="bisaDibayar(p)"
              :to="{ name: 'pembayaran', params: { nomor: p.nomor } }"
              class="tombol tombol--utama"
              :aria-label="`Bayar pesanan ${p.nomor}`"
            >
              Bayar
            </RouterLink>
            <RouterLink
              v-else
              :to="{ name: 'pesanan-detail', params: { nomor: p.nomor } }"
              class="tombol tombol--sekunder"
              :aria-label="`Detail pesanan ${p.nomor}`"
            >
              Detail
            </RouterLink>
          </div>
        </li>
      </ul>

      <NavigasiHalaman :halaman="halaman" :jumlah="jumlahHalaman" :tautan="tautanHalaman" label="Halaman pesanan" />
    </template>
  </div>
</template>

<style scoped>
/* position: relative menahan teks sr-only (posisi absolut) di dalam wadah gulir, agar halaman tidak melebar. */
.tabel-wadah {
  position: relative;
  overflow-x: auto;
  margin-bottom: 16px;
}

.tabel {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9375rem;
}

.tabel th {
  padding: 12px 16px;
  border-bottom: 1px solid var(--garis);
  background: var(--navy-50);
  color: var(--navy);
  font-size: 0.8125rem;
  font-weight: 700;
  text-align: left;
  white-space: nowrap;
}

.tabel th:first-child {
  border-top-left-radius: var(--radius-besar);
}

.tabel th:last-child {
  border-top-right-radius: var(--radius-besar);
}

.tabel td {
  padding: 12px 16px;
  border-bottom: 1px solid var(--garis-lembut);
  vertical-align: middle;
}

.tabel tbody tr:last-child td {
  border-bottom: 0;
}

.tabel tbody tr:hover {
  background: var(--permukaan-redup);
}

.tabel__nomor {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.tabel__isi {
  min-width: 200px;
}

.tabel__angka {
  font-weight: 600;
  text-align: right;
  white-space: nowrap;
}

.tabel__kirim {
  display: block;
  white-space: nowrap;
}

.tabel__redup {
  color: var(--teks-redup);
  white-space: nowrap;
}

.tabel__kecil {
  font-size: 0.8125rem;
}

.tabel__aksi {
  text-align: right;
}

.tombol--kecil {
  min-height: 40px;
  padding: 0 16px;
}

.kartu-pesanan {
  display: none;
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
  .tabel-wadah {
    display: none;
  }

  .kartu-pesanan {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin: 0 0 16px;
    padding: 0;
    list-style: none;
  }

  .kartu-pesanan__item {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 16px;
  }

  .kartu-pesanan__atas {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    justify-content: space-between;
    gap: 4px 12px;
  }

  .kartu-pesanan__nomor {
    display: inline-flex;
    align-items: center;
    min-height: 44px;
    margin-block: -8px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }

  .kartu-pesanan__isi {
    font-size: 0.9375rem;
  }

  .kartu-pesanan__status {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px 12px;
  }

  .kartu-pesanan__bawah {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding-top: 10px;
    border-top: 1px solid var(--garis-lembut);
  }

  .kartu-pesanan__total {
    color: var(--navy);
    font-size: 1.0625rem;
    font-weight: 700;
  }
}
</style>
