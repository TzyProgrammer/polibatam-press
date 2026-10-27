<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { api } from '../../api/klien'
import KotakPesan from '../KotakPesan.vue'

const route = useRoute()

const email = ref(typeof route.query.email === 'string' ? route.query.email : '')
const galat = ref('')
const galatIsian = ref({})
const terkirim = ref('')
const mengirim = ref(false)
// Backend hanya mengirim satu email per akun tiap 60 detik; tombol kirim ulang menunggu selama itu.
const JEDA_DETIK = 60
const sisaDetik = ref(0)
let pewaktu = null

const queryMasuk = computed(() => {
  const { email: _email, ...sisa } = route.query
  return { ...sisa, ...(email.value.trim() ? { email: email.value.trim() } : {}) }
})

function mulaiJeda() {
  sisaDetik.value = JEDA_DETIK
  clearInterval(pewaktu)
  pewaktu = setInterval(() => {
    sisaDetik.value -= 1
    if (sisaDetik.value <= 0) clearInterval(pewaktu)
  }, 1000)
}

onBeforeUnmount(() => clearInterval(pewaktu))

async function kirim() {
  galat.value = ''
  galatIsian.value = {}
  mengirim.value = true
  try {
    const data = await api.post('/auth/lupa-sandi/', { email: email.value.trim() }, { tanpaToken: true })
    terkirim.value = data.detail
    mulaiJeda()
  } catch (e) {
    galatIsian.value = e.isian
    galat.value = Object.keys(e.isian).length ? '' : e.detail
  } finally {
    mengirim.value = false
  }
}
</script>

<template>
  <div class="auth-form">
    <div class="auth-form__kepala">
      <h1 id="judul-lupa-sandi" class="auth-form__judul">Lupa kata sandi</h1>
      <p class="auth-form__sub">
        Masukkan email akun Anda. Kami kirimkan tautan untuk membuat kata sandi baru; tautan berlaku 60 menit.
      </p>
    </div>

    <KotakPesan v-if="terkirim" jenis="sukses">{{ terkirim }}</KotakPesan>
    <KotakPesan v-if="galat" jenis="galat">{{ galat }}</KotakPesan>

    <form class="formulir" novalidate @submit.prevent="kirim">
      <div class="isian">
        <label for="lupa-email" class="isian__label">Email</label>
        <input
          id="lupa-email"
          v-model="email"
          type="email"
          class="isian__kontrol"
          autocomplete="email"
          placeholder="nama@email.com"
          :aria-invalid="galatIsian.email ? 'true' : undefined"
          :aria-describedby="galatIsian.email ? 'lupa-email-galat' : undefined"
        >
        <p v-if="galatIsian.email" id="lupa-email-galat" class="isian__galat">{{ galatIsian.email }}</p>
      </div>

      <button
        type="submit"
        class="tombol tombol--utama tombol--besar tombol--penuh auth-form__kirim"
        :disabled="mengirim || sisaDetik > 0"
      >
        <template v-if="mengirim">Mengirim…</template>
        <template v-else-if="sisaDetik > 0">Kirim ulang dalam {{ sisaDetik }} detik</template>
        <template v-else>{{ terkirim ? 'Kirim ulang tautan' : 'Kirim tautan' }}</template>
      </button>
    </form>

    <p class="auth-form__kaki">
      Sudah ingat kata sandi?
      <RouterLink :to="{ name: 'masuk', query: queryMasuk }">Masuk</RouterLink>
    </p>
  </div>
</template>
