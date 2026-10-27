<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { api } from '../../api/klien'
import { useAuthStore } from '../../stores/auth'
import { usePesanStore } from '../../stores/pesan'
import KotakPesan from '../KotakPesan.vue'
import IsianSandi from './IsianSandi.vue'

const auth = useAuthStore()
const pesan = usePesanStore()
const route = useRoute()
const router = useRouter()

// Tautan email berbentuk /atur-ulang-sandi#uid=...&token=... . Fragmen (#) tidak pernah dikirim peramban
// ke server, dan langsung dihapus dari alamat begitu dibaca agar token tidak tersimpan di riwayat.
const uid = ref('')
const token = ref('')
const keadaan = ref('memeriksa') // memeriksa | siap | tidak-valid
const pesanTidakValid = ref('')
const email = ref('')
const sandi = ref('')
const ulangi = ref('')
const galat = ref('')
const galatIsian = ref({})
const mengirim = ref(false)

onMounted(async () => {
  const data = new URLSearchParams(window.location.hash.replace(/^#/, ''))
  uid.value = data.get('uid') || ''
  token.value = data.get('token') || ''
  if (window.location.hash) {
    window.history.replaceState(window.history.state, '', window.location.pathname + window.location.search)
  }
  if (!uid.value || !token.value) {
    keadaan.value = 'tidak-valid'
    pesanTidakValid.value = 'Tautan atur ulang kata sandi tidak lengkap. Buka tautan dari email, atau minta tautan baru.'
    return
  }
  try {
    const hasil = await api.post('/auth/atur-ulang-sandi/cek/', { uid: uid.value, token: token.value }, { tanpaToken: true })
    email.value = hasil.email
    keadaan.value = 'siap'
  } catch (e) {
    keadaan.value = 'tidak-valid'
    pesanTidakValid.value = e.detail
  }
})

async function kirim() {
  galat.value = ''
  galatIsian.value = {}
  if (sandi.value !== ulangi.value) {
    galatIsian.value = { ulangi: 'Ulangi kata sandi harus sama dengan kata sandi baru.' }
    return
  }
  mengirim.value = true
  try {
    const hasil = await api.post(
      '/auth/atur-ulang-sandi/',
      { uid: uid.value, token: token.value, password: sandi.value },
      { tanpaToken: true },
    )
    // Semua sesi akun ini sudah diakhiri backend, termasuk bila peramban ini sedang masuk.
    auth.bersihkan()
    pesan.tampilkan(hasil.detail, { jenis: 'sukses' })
    router.replace({ name: 'masuk', query: { email: hasil.email } })
  } catch (e) {
    if (e.isian.password) {
      galatIsian.value = { password: e.isian.password }
    } else if (e.status === 400) {
      keadaan.value = 'tidak-valid'
      pesanTidakValid.value = e.detail
    } else {
      galat.value = e.detail
    }
  } finally {
    mengirim.value = false
  }
}
</script>

<template>
  <div class="auth-form">
    <div class="auth-form__kepala">
      <h1 id="judul-atur-ulang-sandi" class="auth-form__judul">Buat kata sandi baru</h1>
      <p v-if="keadaan === 'siap'" class="auth-form__sub">
        Untuk akun <strong>{{ email }}</strong>. Setelah disimpan, semua perangkat yang masih masuk akan dikeluarkan.
      </p>
    </div>

    <div v-if="keadaan === 'memeriksa'" class="auth-form__memuat" aria-busy="true">Memeriksa tautan…</div>

    <template v-else-if="keadaan === 'tidak-valid'">
      <KotakPesan jenis="galat">{{ pesanTidakValid }}</KotakPesan>
      <RouterLink :to="{ name: 'lupa-sandi' }" class="tombol tombol--utama tombol--besar tombol--penuh">
        Minta tautan baru
      </RouterLink>
    </template>

    <template v-else>
      <KotakPesan v-if="galat" jenis="galat">{{ galat }}</KotakPesan>
      <form class="formulir" novalidate @submit.prevent="kirim">
        <IsianSandi
          id="atur-sandi"
          v-model="sandi"
          label="Kata sandi baru"
          autocomplete="new-password"
          :galat="galatIsian.password"
          petunjuk="Minimal 8 karakter; tidak boleh mirip data akun, terlalu umum, atau hanya angka."
        />
        <IsianSandi
          id="atur-ulangi"
          v-model="ulangi"
          label="Ulangi kata sandi baru"
          autocomplete="new-password"
          :galat="galatIsian.ulangi"
        />
        <button type="submit" class="tombol tombol--utama tombol--besar tombol--penuh auth-form__kirim" :disabled="mengirim">
          {{ mengirim ? 'Menyimpan…' : 'Simpan kata sandi baru' }}
        </button>
      </form>
    </template>

    <p class="auth-form__kaki">
      Kembali ke
      <RouterLink :to="{ name: 'masuk' }">halaman Masuk</RouterLink>
    </p>
  </div>
</template>
