<script setup>
import { reactive, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import KotakPesan from '../components/KotakPesan.vue'
import { useAuthStore } from '../stores/auth'
import { usePesanStore } from '../stores/pesan'
import { tujuanAman } from '../utils/navigasi'

const auth = useAuthStore()
const pesan = usePesanStore()
const route = useRoute()
const router = useRouter()

const isian = reactive({ nama_lengkap: '', email: '', no_telepon: '', alamat: '', password: '' })
const ulangi = ref('')
const galat = ref('')
const galatIsian = ref({})
const mengirim = ref(false)

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
  try {
    await auth.masukDengan(data.email, data.password)
    pesan.tampilkan('Akun berhasil dibuat. Selamat datang di Polibatam Press.', { jenis: 'sukses' })
    router.replace(tujuanAman(route.query.next))
  } catch {
    // Akun sudah dibuat, tetapi login otomatis gagal (misalnya terkena batas percobaan): masuk manual.
    pesan.tampilkan('Akun berhasil dibuat. Silakan masuk.', { jenis: 'sukses' })
    router.replace({ name: 'masuk', query: route.query })
  } finally {
    mengirim.value = false
  }
}

function atributIsian(nama) {
  return galatIsian.value[nama] ? { 'aria-invalid': 'true', 'aria-describedby': `daftar-${nama}-galat` } : {}
}
</script>

<template>
  <div class="wadah halaman">
    <section class="kartu auth auth--lebar" aria-labelledby="judul-daftar">
      <div class="auth__kepala">
        <h1 id="judul-daftar" class="auth__judul">Daftar akun</h1>
        <p class="halaman__sub">Akun pembeli untuk membeli buku dan mengajukan ISBN naskah.</p>
      </div>

      <KotakPesan v-if="galat" jenis="galat">{{ galat }}</KotakPesan>

      <form class="formulir" novalidate @submit.prevent="kirim">
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
              v-bind="atributIsian('no_telepon')"
            >
            <p v-if="galatIsian.no_telepon" id="daftar-no_telepon-galat" class="isian__galat">{{ galatIsian.no_telepon }}</p>
            <p v-else class="isian__petunjuk">Contoh: 0812-3456-7890</p>
          </div>
          <div class="isian">
            <label for="daftar-alamat" class="isian__label">Alamat (opsional)</label>
            <textarea
              id="daftar-alamat"
              v-model="isian.alamat"
              rows="2"
              class="isian__kontrol"
              autocomplete="street-address"
              v-bind="atributIsian('alamat')"
            />
            <p v-if="galatIsian.alamat" id="daftar-alamat-galat" class="isian__galat">{{ galatIsian.alamat }}</p>
          </div>
        </div>

        <div class="baris-isian">
          <div class="isian">
            <label for="daftar-sandi" class="isian__label">Kata sandi</label>
            <input
              id="daftar-sandi"
              v-model="isian.password"
              type="password"
              class="isian__kontrol"
              autocomplete="new-password"
              v-bind="atributIsian('password')"
            >
            <p v-if="galatIsian.password" id="daftar-password-galat" class="isian__galat">{{ galatIsian.password }}</p>
          </div>
          <div class="isian">
            <label for="daftar-ulangi" class="isian__label">Ulangi kata sandi</label>
            <input
              id="daftar-ulangi"
              v-model="ulangi"
              type="password"
              class="isian__kontrol"
              autocomplete="new-password"
              v-bind="atributIsian('ulangi')"
            >
            <p v-if="galatIsian.ulangi" id="daftar-ulangi-galat" class="isian__galat">{{ galatIsian.ulangi }}</p>
          </div>
        </div>
        <p class="isian__petunjuk">Minimal 8 karakter; tidak boleh mirip data akun, terlalu umum, atau hanya angka.</p>

        <button type="submit" class="tombol tombol--utama tombol--besar tombol--penuh auth__kirim" :disabled="mengirim">
          {{ mengirim ? 'Memproses…' : 'Daftar' }}
        </button>
      </form>

      <p class="auth__kaki">
        Sudah punya akun?
        <RouterLink :to="{ name: 'masuk', query: route.query }">Masuk</RouterLink>
      </p>
    </section>
  </div>
</template>
