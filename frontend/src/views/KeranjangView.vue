<script setup>
import { computed, nextTick, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { ShoppingCart, Trash2 } from '@lucide/vue'

import KotakPesan from '../components/KotakPesan.vue'
import PenghitungJumlah from '../components/PenghitungJumlah.vue'
import SampulBuku from '../components/SampulBuku.vue'
import { useKeranjangStore } from '../stores/keranjang'
import { usePesanStore } from '../stores/pesan'
import { formatRupiah } from '../utils/format'

// Sama dengan apps.orders.keranjang.BATAS_JUMLAH (backend tetap memeriksa).
const BATAS_JUMLAH = 99

const keranjang = useKeranjangStore()
const pesan = usePesanStore()

const galat = ref('')
const judul = ref(null)
// Per item: sedang disimpan, dan pesan galat dari API (misalnya stok tidak mencukupi).
const sibuk = reactive({})
const galatItem = reactive({})

const isi = computed(() => keranjang.isi)
const daftar = computed(() => isi.value?.item || [])
const adaTidakTersedia = computed(() => daftar.value.some((i) => !i.tersedia))

async function muat() {
  galat.value = ''
  try {
    await keranjang.ambil()
  } catch (e) {
    if (e.status !== 401) galat.value = e.detail
  }
}

// Selalu dimuat ulang saat halaman dibuka: stok dan ketersediaan bisa berubah sejak item ditambahkan.
muat()

function namaProduk(i) {
  return `${i.produk.buku.judul} (${i.produk.format_label})`
}

function cetak(i) {
  return i.produk.format === 'cetak'
}

function maksJumlah(i) {
  return Math.min(BATAS_JUMLAH, i.produk.stok ?? 1)
}

async function jalankan(i, aksi) {
  if (sibuk[i.id]) return false
  sibuk[i.id] = true
  delete galatItem[i.id]
  try {
    await aksi()
    return true
  } catch (e) {
    if (e.status === 404) {
      // Item sudah dihapus dari tab atau perangkat lain.
      await keranjang.muat()
      pesan.tampilkan('Item itu sudah tidak ada di keranjang.', { jenis: 'info' })
    } else if (e.status !== 401) {
      galatItem[i.id] = e.detail
    }
    return false
  } finally {
    delete sibuk[i.id]
  }
}

function ubahJumlah(i, jumlah) {
  jalankan(i, () => keranjang.ubahJumlah(i.id, jumlah))
}

async function hapus(i) {
  const urutan = daftar.value.findIndex((x) => x.id === i.id)
  if (!(await jalankan(i, () => keranjang.hapus(i.id)))) return
  pesan.tampilkan(`${namaProduk(i)} dihapus dari keranjang.`, { jenis: 'info' })
  // Fokus pindah ke tombol hapus item berikutnya (atau judul halaman bila keranjang kosong).
  await nextTick()
  const tombol = document.querySelectorAll('.item-keranjang__hapus')
  const tujuan = tombol[Math.min(urutan, tombol.length - 1)] || judul.value
  tujuan?.focus()
}
</script>

<template>
  <div class="wadah halaman">
    <div class="halaman__kepala">
      <h1 ref="judul" class="halaman__judul" tabindex="-1">Keranjang</h1>
      <p class="halaman__sub">Buku cetak, ebook, dan audiobook bisa dibayar dalam satu pesanan.</p>
    </div>

    <KotakPesan v-if="galat && !isi" jenis="galat">
      <span>{{ galat }}</span>
      <button type="button" class="tombol tombol--sekunder" @click="muat">Coba lagi</button>
    </KotakPesan>

    <div v-else-if="!isi" class="keranjang" aria-busy="true" aria-label="Memuat keranjang">
      <div class="keranjang__daftar">
        <div v-for="n in 3" :key="n" class="kerangka" style="height: 128px" />
      </div>
      <div class="kerangka" style="height: 260px" />
    </div>

    <div v-else-if="!daftar.length" class="kartu kartu--isi kosong">
      <ShoppingCart :size="40" class="kosong__ikon" aria-hidden="true" />
      <h2 class="kosong__judul">Keranjang masih kosong</h2>
      <p class="kosong__teks">Pilih buku cetak, ebook, atau audiobook dari katalog.</p>
      <RouterLink :to="{ name: 'beranda' }" class="tombol tombol--utama">Lihat katalog</RouterLink>
    </div>

    <div v-else class="keranjang">
      <section class="keranjang__daftar" aria-label="Isi keranjang">
        <KotakPesan v-if="galat" jenis="galat">{{ galat }}</KotakPesan>

        <article
          v-for="i in daftar"
          :key="i.id"
          class="item-keranjang"
          :class="{ 'is-tidak-tersedia': !i.tersedia }"
          :aria-labelledby="`item-${i.id}-judul`"
        >
          <RouterLink
            :to="{ name: 'buku', params: { slug: i.produk.buku.slug } }"
            class="item-keranjang__sampul"
            tabindex="-1"
            aria-hidden="true"
          >
            <SampulBuku :src="i.produk.buku.sampul || ''" />
          </RouterLink>

          <div class="item-keranjang__isi">
            <div class="item-keranjang__atas">
              <div class="item-keranjang__teks">
                <h2 :id="`item-${i.id}-judul`" class="item-keranjang__judul">
                  <RouterLink :to="{ name: 'buku', params: { slug: i.produk.buku.slug } }">{{ i.produk.buku.judul }}</RouterLink>
                </h2>
                <p class="item-keranjang__ket">
                  {{ i.produk.format_label }} · {{ formatRupiah(i.produk.harga) }}{{ cetak(i) ? ' per buku' : '' }}
                </p>
                <p v-if="!i.tersedia" class="item-keranjang__status">
                  <strong>{{ i.keterangan }}</strong> · tidak dihitung dalam total
                </p>
              </div>
              <button
                type="button"
                class="tombol-ikon item-keranjang__hapus"
                :aria-label="`Hapus ${namaProduk(i)} dari keranjang`"
                :aria-disabled="sibuk[i.id] ? 'true' : undefined"
                @click="hapus(i)"
              >
                <Trash2 :size="20" />
              </button>
            </div>

            <div class="item-keranjang__bawah">
              <PenghitungJumlah
                v-if="cetak(i) && i.produk.stok > 0"
                :model-value="i.jumlah"
                :max="maksJumlah(i)"
                :sibuk="Boolean(sibuk[i.id])"
                :label="`Jumlah ${i.produk.buku.judul}`"
                @update:model-value="(n) => ubahJumlah(i, n)"
              />
              <span v-else class="item-keranjang__jumlah">Jumlah {{ i.jumlah }}</span>
              <span class="item-keranjang__subtotal">{{ formatRupiah(i.subtotal) }}</span>
            </div>

            <p v-if="galatItem[i.id]" class="item-keranjang__galat" role="alert">{{ galatItem[i.id] }}</p>
          </div>
        </article>

        <p class="keranjang__catatan">
          <template v-if="isi.perlu_pengiriman">Buku cetak dikirim atau diambil sesuai pilihan saat checkout. </template>
          Ebook dan audiobook masuk ke Koleksi setelah pembayaran lunas.
        </p>
      </section>

      <aside class="kartu kartu--isi belanja" aria-labelledby="judul-belanja">
        <h2 id="judul-belanja" class="belanja__judul">Ringkasan belanja</h2>
        <dl class="belanja__rincian">
          <div>
            <dt>{{ adaTidakTersedia ? 'Subtotal (produk tersedia)' : 'Subtotal' }}</dt>
            <dd>{{ formatRupiah(isi.total) }}</dd>
          </div>
          <div v-if="isi.perlu_pengiriman">
            <dt>Ongkir</dt>
            <dd>Dihitung saat checkout</dd>
          </div>
        </dl>
        <p v-if="!isi.semua_tersedia" class="belanja__peringatan">
          Hapus produk yang tidak tersedia atau kurangi jumlahnya untuk melanjutkan ke checkout.
        </p>
        <div class="belanja__lanjut">
          <p class="belanja__total">
            <span>Total</span>
            <span class="belanja__angka">{{ formatRupiah(isi.total) }}</span>
          </p>
          <RouterLink v-if="isi.semua_tersedia" :to="{ name: 'checkout' }" class="tombol tombol--utama tombol--besar tombol--penuh">
            Lanjut ke checkout
          </RouterLink>
          <button v-else type="button" class="tombol tombol--besar tombol--penuh" disabled>Lanjut ke checkout</button>
        </div>
        <p class="belanja__catatan">Pembayaran dengan QRIS melalui Midtrans.</p>
      </aside>

      <!-- Ponsel: total dan tombol checkout tetap terlihat di bawah layar. -->
      <div class="bilah-checkout">
        <p class="bilah-checkout__total">
          <span>Total</span>
          <span class="bilah-checkout__angka">{{ formatRupiah(isi.total) }}</span>
        </p>
        <RouterLink v-if="isi.semua_tersedia" :to="{ name: 'checkout' }" class="tombol tombol--utama tombol--besar">
          Checkout
        </RouterLink>
        <button v-else type="button" class="tombol tombol--besar" disabled>Checkout</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.halaman__judul:focus {
  outline: none;
}

.keranjang {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  align-items: start;
  gap: 24px;
}

.keranjang__daftar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.keranjang__catatan {
  margin-top: 4px;
  color: var(--teks-redup);
  font-size: 0.875rem;
}

.item-keranjang {
  display: flex;
  gap: 16px;
  padding: 16px;
  border: 1px solid var(--garis);
  border-radius: var(--radius-besar);
  background: var(--permukaan);
}

.item-keranjang.is-tidak-tersedia {
  border-style: dashed;
  border-color: var(--garis-isian);
  background: var(--permukaan-redup);
}

.item-keranjang__sampul {
  flex: none;
  align-self: flex-start;
  width: 72px;
  overflow: hidden;
  border: 1px solid var(--garis-lembut);
  border-radius: 6px;
}

.is-tidak-tersedia .item-keranjang__sampul {
  opacity: 0.6;
}

.item-keranjang__isi {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}

.item-keranjang__atas {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.item-keranjang__teks {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.item-keranjang__judul {
  font-family: var(--font-isi);
  font-size: 1rem;
  font-weight: 600;
  line-height: 1.4;
  overflow-wrap: anywhere;
}

.item-keranjang__judul a {
  color: var(--teks);
  text-decoration: none;
}

.item-keranjang__judul a:hover {
  color: var(--navy);
  text-decoration: underline;
}

.item-keranjang__ket {
  color: var(--teks-redup);
  font-size: 0.875rem;
}

.item-keranjang__status {
  color: var(--teks);
  font-size: 0.875rem;
}

.item-keranjang__status strong {
  color: var(--galat);
}

.item-keranjang__hapus {
  flex: none;
  margin: -8px -8px 0 0;
  color: var(--teks-redup);
}

.item-keranjang__hapus:hover {
  background: var(--galat-50);
  color: var(--galat);
}

.item-keranjang__hapus[aria-disabled='true'] {
  cursor: progress;
}

.item-keranjang__bawah {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 16px;
}

.item-keranjang__jumlah {
  color: var(--teks-redup);
  font-size: 0.875rem;
}

.item-keranjang__subtotal {
  margin-left: auto;
  color: var(--navy);
  font-size: 1rem;
  font-weight: 700;
}

.is-tidak-tersedia .item-keranjang__subtotal {
  color: var(--teks-redup);
  text-decoration: line-through;
}

.item-keranjang__galat {
  color: var(--galat);
  font-size: 0.8125rem;
  font-weight: 600;
}

/* Ringkasan belanja */
.belanja {
  position: sticky;
  top: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.belanja__judul {
  font-size: 1.125rem;
}

.belanja__rincian {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0;
}

.belanja__rincian div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.belanja__rincian dt {
  color: var(--teks-redup);
}

.belanja__rincian dd {
  margin: 0;
  text-align: right;
}

.belanja__peringatan {
  padding: 10px 12px;
  border-radius: var(--radius-kecil);
  background: var(--galat-50);
  color: var(--galat);
  font-size: 0.875rem;
  font-weight: 600;
}

.belanja__lanjut {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.belanja__total {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding-top: 16px;
  border-top: 1px solid var(--garis-lembut);
  font-weight: 700;
}

.belanja__angka {
  color: var(--navy);
  font-size: 1.375rem;
}

.belanja__catatan {
  color: var(--teks-redup);
  font-size: 0.8125rem;
  text-align: center;
}

.bilah-checkout {
  display: none;
}

/* Keranjang kosong */
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

@media (max-width: 959px) {
  .keranjang {
    grid-template-columns: minmax(0, 1fr) 300px;
  }
}

@media (max-width: 719px) {
  .keranjang {
    grid-template-columns: minmax(0, 1fr);
    gap: 16px;
  }

  .item-keranjang {
    gap: 12px;
    padding: 12px;
  }

  .item-keranjang__sampul {
    width: 64px;
  }

  .belanja {
    position: static;
  }

  /* Total dan tombol pindah ke bilah bawah. */
  .belanja__lanjut,
  .belanja__catatan {
    display: none;
  }

  .bilah-checkout {
    position: sticky;
    bottom: 0;
    z-index: 5;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-inline: -16px;
    padding: 12px 16px;
    border-top: 1px solid var(--garis);
    background: var(--permukaan);
    box-shadow: 0 -6px 16px rgba(20, 38, 77, 0.08);
  }

  .bilah-checkout__total {
    display: flex;
    flex-direction: column;
    line-height: 1.3;
  }

  .bilah-checkout__total span:first-child {
    color: var(--teks-redup);
    font-size: 0.8125rem;
  }

  .bilah-checkout__angka {
    color: var(--navy);
    font-size: 1.125rem;
    font-weight: 700;
  }

  .bilah-checkout .tombol {
    padding-inline: 28px;
  }
}
</style>
