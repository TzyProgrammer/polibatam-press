<script setup>
import { computed, reactive, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '../../stores/auth'
import { usePesanStore } from '../../stores/pesan'
import { KECAMATAN_KOTA_BATAM } from '../../utils/wilayah'
import KotakPesan from '../KotakPesan.vue'
import IsianSandi from './IsianSandi.vue'

const auth = useAuthStore()
const pesan = usePesanStore()
const route = useRoute()
const router = useRouter()

const isian = reactive({ nama_lengkap: '', email: '', no_telepon: '', kecamatan: '', alamat: '', password: '' })
const ulangi = ref('')
const galat = ref('')
const galatIsian = ref({})
const mengirim = ref(false)

const queryLanjut = computed(() => {
  const { email: _email, ...sisa } = route.query
  return sisa
})

// Setelah akun dibuat, pembeli diarahkan ke halaman Masuk dengan email terisi (tanpa login otomatis).
async function kirim() {
  galat.value = ''
  galatIsian.value = {}
  if (isian.password !== ulangi.value) {
    galatIsian.value = { ulangi: 'Ulangi kata sandi harus sama dengan kata sandi.' }
    return
  }
  mengirim.value = true
  const data = { ...isian, email: isian.email.trim() }
  try {
    await auth.daftar(data)
  } catch (e) {
    galatIsian.value = e.isian
    galat.value = Object.keys(e.isian).length ? '' : e.detail
    mengirim.value = false
    return
  }
  mengirim.value = false
  pesan.tampilkan('Akun berhasil dibuat. Silakan masuk dengan email dan kata sandi Anda.', { jenis: 'sukses' })
  router.replace({ name: 'masuk', query: { ...queryLanjut.value, email: data.email.toLowerCase() } })
}

function atributIsian(nama) {
  return galatIsian.value[nama] ? { 'aria-invalid': 'true', 'aria-describedby': `daftar-${nama}-galat` } : {}
}
</script>

<template>
  <div class="auth-form">
    <div class="auth-form__kepala">
      <h1 id="judul-daftar" class="auth-form__judul">Daftar akun</h1>
      <p class="auth-form__sub">Akun pembeli untuk membeli buku dan mengajukan ISBN naskah.</p>
    </div>

    <KotakPesan v-if="galat" jenis="galat">{{ galat }}</KotakPesan>

    <form class="formulir formulir--rapat" novalidate @submit.prevent="kirim">
      <div class="baris-isian">
        <div class="isian">
          <label for="daftar-nama" class="isian__label">Nama lengkap</label>
          <input
            id="daftar-nama"
            v-model="isian.nama_lengkap"
            type="text"
            class="isian__kontrol"
            autocomplete="name"
            v-bind="atributIsian('nama_lengkap')"
          >
          <p v-if="galatIsian.nama_lengkap" id="daftar-nama_lengkap-galat" class="isian__galat">{{ galatIsian.nama_lengkap }}</p>
        </div>
        <div class="isian">
          <label for="daftar-email" class="isian__label">Email</label>
          <input
            id="daftar-email"
            v-model="isian.email"
            type="email"
            class="isian__kontrol"
            autocomplete="email"
            placeholder="nama@email.com"
            v-bind="atributIsian('email')"
          >
          <p v-if="galatIsian.email" id="daftar-email-galat" class="isian__galat">{{ galatIsian.email }}</p>
        </div>
      </div>

      <div class="baris-isian">
        <div class="isian">
          <label for="daftar-telepon" class="isian__label">Nomor telepon (opsional)</label>
          <input
            id="daftar-telepon"
            v-model="isian.no_telepon"
            type="tel"
            class="isian__kontrol"
            autocomplete="tel"
            placeholder="0812-3456-7890"
            v-bind="atributIsian('no_telepon')"
          >
          <p v-if="galatIsian.no_telepon" id="daftar-no_telepon-galat" class="isian__galat">{{ galatIsian.no_telepon }}</p>
        </div>
        <div class="isian">
          <label for="daftar-kecamatan" class="isian__label">Kecamatan (opsional)</label>
          <select id="daftar-kecamatan" v-model="isian.kecamatan" class="isian__kontrol" v-bind="atributIsian('kecamatan')">
            <option value="">Pilih kecamatan</option>
            <option v-for="k in KECAMATAN_KOTA_BATAM" :key="k" :value="k">{{ k }}</option>
          </select>
          <p v-if="galatIsian.kecamatan" id="daftar-kecamatan-galat" class="isian__galat">{{ galatIsian.kecamatan }}</p>
        </div>
      </div>

      <div class="isian">
        <label for="daftar-alamat" class="isian__label">Alamat (opsional)</label>
        <textarea
          id="daftar-alamat"
          v-model="isian.alamat"
          rows="2"
          class="isian__kontrol"
          autocomplete="street-address"
          placeholder="Nama jalan, perumahan, blok, nomor rumah"
          v-bind="atributIsian('alamat')"
        />
        <p v-if="galatIsian.alamat" id="daftar-alamat-galat" class="isian__galat">{{ galatIsian.alamat }}</p>
        <p v-else class="isian__petunjuk">Telepon, kecamatan, dan alamat dipakai mengisi otomatis checkout delivery.</p>
      </div>

      <div class="baris-isian">
        <IsianSandi
          id="daftar-sandi"
          v-model="isian.password"
          label="Kata sandi"
          autocomplete="new-password"
          :galat="galatIsian.password"
        />
        <IsianSandi
          id="daftar-ulangi"
          v-model="ulangi"
          label="Ulangi kata sandi"
          autocomplete="new-password"
          :galat="galatIsian.ulangi"
        />
      </div>
      <p class="isian__petunjuk">Minimal 8 karakter; tidak boleh mirip data akun, terlalu umum, atau hanya angka.</p>

      <button type="submit" class="tombol tombol--utama tombol--besar tombol--penuh auth-form__kirim" :disabled="mengirim">
        {{ mengirim ? 'Memproses…' : 'Daftar' }}
      </button>
    </form>

    <p class="auth-form__kaki">
      Sudah punya akun?
      <RouterLink :to="{ name: 'masuk', query: queryLanjut }">Masuk</RouterLink>
    </p>
  </div>
</template>
