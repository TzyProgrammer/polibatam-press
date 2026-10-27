<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { Check, QrCode, Store, Truck } from '@lucide/vue'

import { api } from '../api/klien'
import KotakPesan from '../components/KotakPesan.vue'
import LangkahBeli from '../components/LangkahBeli.vue'
import ModalKonfirmasi from '../components/ModalKonfirmasi.vue'
import RingkasanPesanan from '../components/RingkasanPesanan.vue'
import { useAuthStore } from '../stores/auth'
import { useKeranjangStore } from '../stores/keranjang'
import { formatRupiah } from '../utils/format'
import { tandaiBukaOtomatis } from '../utils/snap'

const auth = useAuthStore()
const keranjang = useKeranjangStore()
const router = useRouter()

// GET /api/pesanan/checkout/: {keranjang, pengiriman: {delivery, takeaway}, batas_bayar_menit, metode_pembayaran}
const opsi = ref(null)
const galatMuat = ref('')
// { teks, keKeranjang }: keKeranjang bila isi keranjang yang bermasalah (400), bukan gangguan Midtrans (502/503).
const galat = ref(null)
const galatIsian = ref({})
const mengirim = ref(false)

// Nama, telepon, alamat, dan kecamatan diisi dari profil; boleh diubah untuk pesanan ini. Telepon, alamat, dan
// kecamatan yang diketik juga disimpan ke profil (revisi Tahap R): kolom profil yang masih kosong langsung
// diisi backend, sedangkan kolom yang sudah berisi nilai lain hanya diganti bila pembeli menyetujui modal.
const isian = reactive({
  metode_pengiriman: '',
  nama_penerima: auth.pengguna?.nama_lengkap || '',
  no_telepon_penerima: auth.pengguna?.no_telepon || '',
  alamat: auth.pengguna?.alamat || '',
  kecamatan: '',
})

const LABEL_PROFIL = { no_telepon: 'Nomor telepon', alamat: 'Alamat', kecamatan: 'Kecamatan' }

function rapikan(teks) {
  return (teks || '').split(/\s+/).filter(Boolean).join(' ')
}

// Kolom profil yang akan berubah nilainya bila isian checkout disimpan ke profil.
function perubahanProfil() {
  const profil = auth.pengguna || {}
  const baru = { no_telepon: isian.no_telepon_penerima.trim() }
  if (isian.metode_pengiriman === 'delivery') {
    baru.alamat = rapikan(isian.alamat)
    baru.kecamatan = isian.kecamatan
  }
  return Object.entries(baru)
    .filter(([kolom, nilai]) => nilai && rapikan(profil[kolom]) && rapikan(profil[kolom]) !== nilai)
    .map(([kolom, nilai]) => ({ kolom, label: LABEL_PROFIL[kolom], lama: rapikan(profil[kolom]), baru: nilai }))
}

// Modal "perbarui profil?": diselesaikan dengan true (perbarui), false (pesanan ini saja), atau null (batal).
const modalProfil = reactive({ buka: false, perubahan: [] })
let jawabModal = null

function tanyaPerbaruiProfil(perubahan) {
  modalProfil.perubahan = perubahan
  modalProfil.buka = true
  return new Promise((selesai) => {
    jawabModal = (jawaban) => {
      modalProfil.buka = false
      jawabModal = null
      selesai(jawaban)
    }
  })
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

async function muat() {
  galatMuat.value = ''
  try {
    const data = await api.get('/pesanan/checkout/')
    opsi.value = data
    keranjang.simpan(data.keranjang)
    // Kecamatan profil dipakai bila termasuk daftar kecamatan delivery.
    const kecamatanProfil = auth.pengguna?.kecamatan
    if (!isian.kecamatan && data.pengiriman.delivery.kecamatan.includes(kecamatanProfil)) {
      isian.kecamatan = kecamatanProfil
    }
  } catch (e) {
    if (e.status !== 401) galatMuat.value = e.detail
  }
}

muat()

const isi = computed(() => opsi.value?.keranjang)
const perluKirim = computed(() => Boolean(isi.value?.perlu_pengiriman))
const delivery = computed(() => isi.value && opsi.value.pengiriman.delivery)
const takeaway = computed(() => isi.value && opsi.value.pengiriman.takeaway)
const siap = computed(() => Boolean(isi.value?.item.length && isi.value.semua_tersedia))

const ongkir = computed(() => {
  if (isian.metode_pengiriman === 'delivery') return delivery.value.ongkir
  return 0
})

const total = computed(() => (isi.value?.total || 0) + (perluKirim.value ? ongkir.value : 0))

const barisRingkasan = computed(() =>
  (isi.value?.item || []).map((i) => ({
    kunci: i.id,
    judul: i.produk.buku.judul,
    keterangan: i.produk.format === 'cetak' ? `${i.produk.format_label} × ${i.jumlah}` : i.produk.format_label,
    harga: i.subtotal,
  })),
)

const rincian = computed(() => {
  const hasil = [{ label: 'Subtotal', nilai: isi.value?.total || 0 }]
  if (perluKirim.value) {
    let nilai = 'Pilih metode pengiriman'
    if (isian.metode_pengiriman === 'delivery') nilai = ongkir.value
    if (isian.metode_pengiriman === 'takeaway') nilai = 'Gratis'
    hasil.push({ label: 'Ongkir', nilai })
  }
  return hasil
})

// Pemeriksaan di peramban hanya untuk kenyamanan; backend tetap memeriksa semuanya (pesan sama).
function periksa() {
  const hasil = {}
  if (!perluKirim.value) return hasil
  if (!isian.metode_pengiriman) {
    hasil.metode_pengiriman = 'Pilih metode pengiriman: delivery (Kota Batam) atau takeaway.'
    return hasil
  }
  if (!isian.nama_penerima.trim()) hasil.nama_penerima = 'Nama penerima wajib diisi.'
  if (!isian.no_telepon_penerima.trim()) {
    hasil.no_telepon_penerima = 'Nomor telepon wajib diisi agar penerima bisa dihubungi.'
  }
  if (isian.metode_pengiriman === 'delivery') {
    if (!isian.alamat.trim()) hasil.alamat = 'Alamat pengiriman wajib diisi untuk delivery.'
    if (!isian.kecamatan) hasil.kecamatan = 'Pilih kecamatan di Kota Batam (delivery hanya untuk area Kota Batam).'
  }
  return hasil
}

const URUTAN_ISIAN = [
  ['metode_pengiriman', 'checkout-metode-delivery'],
  ['nama_penerima', 'checkout-nama'],
  ['no_telepon_penerima', 'checkout-telepon'],
  ['alamat', 'checkout-alamat'],
  ['kecamatan', 'checkout-kecamatan'],
]

async function fokusGalatPertama() {
  await nextTick()
  const pertama = URUTAN_ISIAN.find(([nama]) => galatIsian.value[nama])
  document.getElementById(pertama?.[1])?.focus()
}

function atributIsian(nama, id) {
  if (!galatIsian.value[nama]) return {}
  return { 'aria-invalid': 'true', 'aria-describedby': `${id}-galat` }
}

function dataKirim(simpanKeProfil) {
  if (!perluKirim.value) return {}
  const data = {
    metode_pengiriman: isian.metode_pengiriman,
    nama_penerima: isian.nama_penerima.trim(),
    no_telepon_penerima: isian.no_telepon_penerima.trim(),
    simpan_ke_profil: simpanKeProfil,
  }
  if (isian.metode_pengiriman === 'delivery') {
    data.alamat = isian.alamat.trim()
    data.kecamatan = isian.kecamatan
  }
  return data
}

async function buatPesanan() {
  if (mengirim.value || !siap.value) return
  galat.value = null
  galatIsian.value = periksa()
  if (Object.keys(galatIsian.value).length) {
    fokusGalatPertama()
    return
  }
  let simpanKeProfil = false
  const perubahan = perluKirim.value ? perubahanProfil() : []
  if (perubahan.length) {
    const jawaban = await tanyaPerbaruiProfil(perubahan)
    if (jawaban === null) return
    simpanKeProfil = jawaban
  }
  mengirim.value = true
  try {
    const pesanan = await api.post('/pesanan/checkout/', dataKirim(simpanKeProfil))
    // Keranjang sudah dikosongkan backend saat pesanan dibuat; profil mungkin ikut diperbarui.
    keranjang.muat()
    auth.muatProfil()
    tandaiBukaOtomatis(pesanan.nomor)
    await router.replace({ name: 'pembayaran', params: { nomor: pesanan.nomor } })
  } catch (e) {
    if (e.status === 401) return
    if (Object.keys(e.isian).length) {
      galatIsian.value = e.isian
      fokusGalatPertama()
      return
    }
    galat.value = { teks: e.detail, keKeranjang: e.status === 400 }
    // 400: isi keranjang berubah (stok habis, produk tidak dijual lagi). Tampilkan keadaan terbaru.
    if (e.status === 400) muat()
    await nextTick()
    document.getElementById('checkout-galat')?.focus()
  } finally {
    mengirim.value = false
  }
}
</script>

<template>
  <div class="wadah halaman">
    <div class="halaman__kepala">
      <h1 class="halaman__judul">Checkout</h1>
      <p class="halaman__sub">
        {{ perluKirim ? 'Periksa pengiriman dan isi pesanan sebelum membayar.' : 'Periksa isi pesanan sebelum membayar.' }}
      </p>
    </div>

    <KotakPesan v-if="galatMuat && !opsi" jenis="galat">
      <span>{{ galatMuat }}</span>
      <button type="button" class="tombol tombol--sekunder" @click="muat">Coba lagi</button>
    </KotakPesan>

    <div v-else-if="!opsi" class="checkout" aria-busy="true" aria-label="Memuat checkout">
      <div class="kerangka" style="height: 420px" />
      <div class="kerangka" style="height: 320px" />
    </div>

    <div v-else-if="!isi.item.length" class="kartu kartu--isi kosong">
      <h2 class="kosong__judul">Keranjang Anda kosong</h2>
      <p class="kosong__teks">Tambahkan buku ke keranjang sebelum checkout.</p>
      <RouterLink :to="{ name: 'beranda' }" class="tombol tombol--utama">Lihat katalog</RouterLink>
    </div>

    <template v-else>
      <LangkahBeli :aktif="2" :tanpa-pengiriman="!perluKirim" />

      <div class="checkout">
        <form id="form-checkout" class="checkout__form" novalidate @submit.prevent="buatPesanan">
          <div v-if="galat" id="checkout-galat" tabindex="-1" class="checkout__galat">
            <KotakPesan jenis="galat">
              <span>{{ galat.teks }}</span>
              <RouterLink v-if="galat.keKeranjang" :to="{ name: 'keranjang' }">Kembali ke keranjang</RouterLink>
            </KotakPesan>
          </div>

          <KotakPesan v-else-if="!isi.semua_tersedia" jenis="galat">
            <span>Ada produk yang belum bisa dibeli. Perbarui keranjang terlebih dahulu.</span>
            <RouterLink :to="{ name: 'keranjang' }">Kembali ke keranjang</RouterLink>
          </KotakPesan>

          <template v-if="perluKirim">
            <div class="kartu kartu--isi">
              <fieldset class="opsi" :aria-describedby="galatIsian.metode_pengiriman ? 'checkout-metode-galat' : undefined">
                <legend class="opsi__judul">Metode pengiriman</legend>
                <label class="opsi__pilihan" :class="{ 'is-dipilih': isian.metode_pengiriman === 'delivery' }">
                  <input
                    id="checkout-metode-delivery"
                    v-model="isian.metode_pengiriman"
                    type="radio"
                    name="metode_pengiriman"
                    value="delivery"
                  >
                  <Truck :size="24" class="opsi__ikon" aria-hidden="true" />
                  <span class="opsi__teks">
                    <span class="opsi__nama">{{ delivery.label }}</span>
                    <span class="opsi__ket">
                      Diantar ke alamat Anda di salah satu dari {{ delivery.kecamatan.length }} kecamatan Kota Batam.
                    </span>
                  </span>
                  <span class="opsi__harga">{{ formatRupiah(delivery.ongkir) }}</span>
                </label>
                <label class="opsi__pilihan" :class="{ 'is-dipilih': isian.metode_pengiriman === 'takeaway' }">
                  <input
                    id="checkout-metode-takeaway"
                    v-model="isian.metode_pengiriman"
                    type="radio"
                    name="metode_pengiriman"
                    value="takeaway"
                  >
                  <Store :size="24" class="opsi__ikon" aria-hidden="true" />
                  <span class="opsi__teks">
                    <span class="opsi__nama">{{ takeaway.label }}</span>
                    <span class="opsi__ket">{{ takeaway.lokasi }}.</span>
                  </span>
                  <span class="opsi__harga">Gratis</span>
                </label>
                <p v-if="galatIsian.metode_pengiriman" id="checkout-metode-galat" class="isian__galat">
                  {{ galatIsian.metode_pengiriman }}
                </p>
              </fieldset>
            </div>

            <section v-if="isian.metode_pengiriman" class="kartu kartu--isi penerima" aria-labelledby="judul-penerima">
              <h2 id="judul-penerima" class="penerima__judul">
                {{ isian.metode_pengiriman === 'delivery' ? 'Data penerima' : 'Data pengambil' }}
              </h2>
              <div class="baris-isian">
                <div class="isian">
                  <label for="checkout-nama" class="isian__label">
                    {{ isian.metode_pengiriman === 'delivery' ? 'Nama penerima' : 'Nama pengambil' }}
                  </label>
                  <input
                    id="checkout-nama"
                    v-model="isian.nama_penerima"
                    type="text"
                    class="isian__kontrol"
                    autocomplete="name"
                    maxlength="150"
                    v-bind="atributIsian('nama_penerima', 'checkout-nama')"
                  >
                  <p v-if="galatIsian.nama_penerima" id="checkout-nama-galat" class="isian__galat">
                    {{ galatIsian.nama_penerima }}
                  </p>
                </div>
                <div class="isian">
                  <label for="checkout-telepon" class="isian__label">Nomor telepon</label>
                  <input
                    id="checkout-telepon"
                    v-model="isian.no_telepon_penerima"
                    type="tel"
                    class="isian__kontrol"
                    autocomplete="tel"
                    inputmode="tel"
                    maxlength="20"
                    v-bind="atributIsian('no_telepon_penerima', 'checkout-telepon')"
                  >
                  <p v-if="galatIsian.no_telepon_penerima" id="checkout-telepon-galat" class="isian__galat">
                    {{ galatIsian.no_telepon_penerima }}
                  </p>
                </div>
              </div>
              <p class="isian__petunjuk">
                Data diisi dari profil dan boleh diubah. Telepon{{ isian.metode_pengiriman === 'delivery' ? ', alamat, dan kecamatan' : '' }}
                yang baru juga bisa disimpan ke profil.
              </p>

              <template v-if="isian.metode_pengiriman === 'delivery'">
                <div class="isian">
                  <label for="checkout-alamat" class="isian__label">Alamat</label>
                  <textarea
                    id="checkout-alamat"
                    v-model="isian.alamat"
                    class="isian__kontrol"
                    rows="3"
                    maxlength="400"
                    autocomplete="street-address"
                    placeholder="Nama jalan, nomor rumah, RT/RW, kelurahan"
                    v-bind="atributIsian('alamat', 'checkout-alamat')"
                  />
                  <p v-if="galatIsian.alamat" id="checkout-alamat-galat" class="isian__galat">{{ galatIsian.alamat }}</p>
                </div>
                <div class="baris-isian">
                  <div class="isian">
                    <label for="checkout-kecamatan" class="isian__label">Kecamatan</label>
                    <select
                      id="checkout-kecamatan"
                      v-model="isian.kecamatan"
                      class="isian__kontrol"
                      v-bind="atributIsian('kecamatan', 'checkout-kecamatan')"
                    >
                      <option value="">Pilih kecamatan</option>
                      <option v-for="k in delivery.kecamatan" :key="k" :value="k">{{ k }}</option>
                    </select>
                    <p v-if="galatIsian.kecamatan" id="checkout-kecamatan-galat" class="isian__galat">
                      {{ galatIsian.kecamatan }}
                    </p>
                  </div>
                  <div class="isian">
                    <label for="checkout-kota" class="isian__label">Kota</label>
                    <input id="checkout-kota" type="text" class="isian__kontrol" value="Kota Batam" readonly>
                  </div>
                </div>
              </template>

              <p v-else class="penerima__lokasi">
                Ambil pesanan di <strong>{{ takeaway.lokasi }}</strong> setelah statusnya <strong>Siap diambil</strong>.
                Pemberitahuan muncul di ikon lonceng.
              </p>
            </section>
          </template>

          <KotakPesan v-else jenis="info">
            Semua produk di pesanan ini digital, jadi tidak perlu pengiriman. Setelah pembayaran lunas, ebook dan audiobook
            langsung tersedia di Koleksi.
          </KotakPesan>

          <div class="kartu kartu--isi">
            <fieldset class="opsi">
              <legend class="opsi__judul">Pembayaran</legend>
              <div class="opsi__pilihan is-dipilih opsi__pilihan--tetap">
                <QrCode :size="24" class="opsi__ikon" aria-hidden="true" />
                <span class="opsi__teks">
                  <span class="opsi__nama">QRIS melalui Midtrans</span>
                  <span class="opsi__ket">
                    Bayar dalam {{ opsi.batas_bayar_menit }} menit setelah pesanan dibuat dengan aplikasi e-wallet atau mobile
                    banking yang mendukung QRIS.
                  </span>
                </span>
                <Check :size="20" class="opsi__centang" aria-hidden="true" />
              </div>
            </fieldset>
          </div>
        </form>

        <RingkasanPesanan
          class="checkout__ringkasan"
          id-judul="judul-ringkasan-checkout"
          :baris="barisRingkasan"
          :rincian="rincian"
          :total="total"
        >
          <template #kepala>
            <RouterLink :to="{ name: 'keranjang' }" class="ringkasan__ubah">Ubah keranjang</RouterLink>
          </template>
          <button
            type="submit"
            form="form-checkout"
            class="tombol tombol--utama tombol--besar tombol--penuh"
            :disabled="mengirim || !siap"
          >
            {{ mengirim ? 'Membuat pesanan…' : 'Buat pesanan dan bayar' }}
          </button>
          <p v-if="perluKirim" class="checkout__catatan">
            Stok buku cetak disimpan untuk Anda sampai batas waktu pembayaran.
          </p>
        </RingkasanPesanan>
      </div>
    </template>

    <ModalKonfirmasi
      :buka="modalProfil.buka"
      judul="Ubah data di profil?"
      label-ya="Ya, ubah profil"
      label-tidak="Tidak, untuk pesanan ini saja"
      @ya="jawabModal?.(true)"
      @tidak="jawabModal?.(false)"
      @batal="jawabModal?.(null)"
    >
      <p>Data pengiriman yang Anda isi berbeda dengan data di profil. Apakah Anda yakin ingin mengubah data profil?</p>
      <dl class="perubahan">
        <div v-for="ubah in modalProfil.perubahan" :key="ubah.kolom" class="perubahan__baris">
          <dt>{{ ubah.label }}</dt>
          <dd>
            <span class="perubahan__lama">{{ ubah.lama }}</span>
            <span class="perubahan__panah" aria-hidden="true">→</span>
            <span class="sr-only">menjadi</span>
            <span class="perubahan__baru">{{ ubah.baru }}</span>
          </dd>
        </div>
      </dl>
      <p class="perubahan__catatan">Pilihan mana pun, pesanan ini tetap memakai data yang Anda isi.</p>
    </ModalKonfirmasi>
  </div>
</template>

<style scoped>
.perubahan {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 0;
  padding: 12px 14px;
  border: 1px solid var(--garis-lembut);
  border-radius: var(--radius);
  background: var(--latar);
}

.perubahan__baris dt {
  color: var(--teks-redup);
  font-size: 0.8125rem;
  font-weight: 600;
}

.perubahan__baris dd {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 8px;
  margin: 0;
  overflow-wrap: anywhere;
}

.perubahan__lama {
  color: var(--teks-redup);
  text-decoration: line-through;
}

.perubahan__panah {
  color: var(--teks-redup);
}

.perubahan__baru {
  font-weight: 600;
}

.perubahan__catatan {
  color: var(--teks-redup);
  font-size: 0.875rem;
}

.checkout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 380px;
  align-items: start;
  gap: 24px;
}

.checkout__form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.checkout__galat:focus {
  outline: none;
}

.checkout__ringkasan {
  position: sticky;
  top: 16px;
}

.ringkasan__ubah {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  margin-block: -12px;
  font-size: 0.875rem;
  font-weight: 600;
}

.checkout__catatan {
  color: var(--teks-redup);
  font-size: 0.8125rem;
  text-align: center;
}

/* Pilihan pengiriman dan pembayaran */
.opsi {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
}

.opsi__judul {
  margin-bottom: 14px;
  padding: 0;
  font-family: var(--font-judul);
  font-size: 1.125rem;
  font-weight: 700;
}

.opsi__pilihan {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  border: 1px solid var(--garis);
  border-radius: var(--radius);
  background: var(--permukaan);
  cursor: pointer;
}

.opsi__pilihan:hover {
  border-color: var(--navy);
}

.opsi__pilihan.is-dipilih {
  border-color: var(--navy);
  box-shadow: inset 0 0 0 1px var(--navy);
  background: var(--navy-50);
}

.opsi__pilihan--tetap {
  cursor: default;
}

.opsi__pilihan input {
  flex: none;
  width: 20px;
  height: 20px;
  margin: 0;
  accent-color: var(--navy);
}

.opsi__pilihan:has(input:focus-visible) {
  outline: 3px solid var(--navy);
  outline-offset: 2px;
}

.opsi__ikon,
.opsi__centang {
  flex: none;
  color: var(--navy);
}

.opsi__teks {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.opsi__nama {
  font-weight: 600;
}

.opsi__ket {
  color: var(--teks-redup);
  font-size: 0.8125rem;
}

.opsi__harga {
  flex: none;
  color: var(--navy);
  font-weight: 700;
}

/* Data penerima */
.penerima {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.penerima__judul {
  font-size: 1.125rem;
}

.penerima__lokasi {
  padding: 12px 14px;
  border-radius: var(--radius-kecil);
  background: var(--biru-50);
  font-size: 0.9375rem;
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
  .checkout {
    grid-template-columns: minmax(0, 1fr) 320px;
  }
}

@media (max-width: 719px) {
  .checkout {
    grid-template-columns: minmax(0, 1fr);
    gap: 16px;
  }

  .checkout__ringkasan {
    position: static;
  }

  .opsi__pilihan {
    align-items: flex-start;
    gap: 12px;
    padding: 12px;
  }

  .opsi__ikon {
    display: none;
  }
}
</style>
