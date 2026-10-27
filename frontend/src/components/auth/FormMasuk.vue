<script setup>
import { computed, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '../../stores/auth'
import { tujuanAman } from '../../utils/navigasi'
import KotakPesan from '../KotakPesan.vue'
import IsianSandi from './IsianSandi.vue'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

// Email terisi otomatis setelah mendaftar atau mengatur ulang kata sandi (?email=...).
const email = ref(typeof route.query.email === 'string' ? route.query.email : '')
const sandi = ref('')
const galat = ref('')
const galatIsian = ref({})
const mengirim = ref(false)

// Query selain email (misalnya next) dibawa ke halaman Daftar dan Lupa kata sandi.
const queryLanjut = computed(() => {
  const { email: _email, ...sisa } = route.query
  return sisa
})

async function kirim() {
  galat.value = ''
  galatIsian.value = {}
  mengirim.value = true
  try {
    await auth.masukDengan(email.value.trim(), sandi.value)
    router.replace(tujuanAman(route.query.next))
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
      <h1 id="judul-masuk" class="auth-form__judul">Masuk</h1>
      <p class="auth-form__sub">Masuk untuk membeli buku, membuka Koleksi, dan mengajukan ISBN.</p>
    </div>

    <KotakPesan v-if="galat" jenis="galat">{{ galat }}</KotakPesan>

    <form class="formulir" novalidate @submit.prevent="kirim">
      <div class="isian">
        <label for="masuk-email" class="isian__label">Email</label>
        <input
          id="masuk-email"
          v-model="email"
          type="email"
          class="isian__kontrol"
          autocomplete="email"
          placeholder="nama@email.com"
          :aria-invalid="galatIsian.email ? 'true' : undefined"
          :aria-describedby="galatIsian.email ? 'masuk-email-galat' : undefined"
        >
        <p v-if="galatIsian.email" id="masuk-email-galat" class="isian__galat">{{ galatIsian.email }}</p>
      </div>

      <IsianSandi id="masuk-sandi" v-model="sandi" label="Kata sandi" :galat="galatIsian.password" />

      <RouterLink
        class="auth-form__lupa"
        :to="{ name: 'lupa-sandi', query: { ...queryLanjut, ...(email.trim() ? { email: email.trim() } : {}) } }"
      >
        Lupa kata sandi?
      </RouterLink>

      <button type="submit" class="tombol tombol--utama tombol--besar tombol--penuh auth-form__kirim" :disabled="mengirim">
        {{ mengirim ? 'Memproses…' : 'Masuk' }}
      </button>
    </form>

    <p class="auth-form__kaki">
      Belum punya akun?
      <RouterLink :to="{ name: 'daftar', query: queryLanjut }">Daftar</RouterLink>
    </p>
  </div>
</template>
