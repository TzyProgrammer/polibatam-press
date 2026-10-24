<script setup>
import { ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { Eye, EyeOff } from '@lucide/vue'

import KotakPesan from '../components/KotakPesan.vue'
import { useAuthStore } from '../stores/auth'
import { tujuanAman } from '../utils/navigasi'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const email = ref('')
const sandi = ref('')
const lihatSandi = ref(false)
const galat = ref('')
const galatIsian = ref({})
const mengirim = ref(false)

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
  <div class="wadah halaman">
    <section class="kartu auth" aria-labelledby="judul-masuk">
      <div class="auth__kepala">
        <h1 id="judul-masuk" class="auth__judul">Masuk</h1>
        <p class="halaman__sub">Masuk untuk membeli buku, membuka Koleksi, dan mengajukan ISBN.</p>
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

        <div class="isian">
          <label for="masuk-sandi" class="isian__label">Kata sandi</label>
          <div class="sandi">
            <input
              id="masuk-sandi"
              v-model="sandi"
              :type="lihatSandi ? 'text' : 'password'"
              class="isian__kontrol"
              autocomplete="current-password"
              :aria-invalid="galatIsian.password ? 'true' : undefined"
              :aria-describedby="galatIsian.password ? 'masuk-sandi-galat' : undefined"
            >
            <button
              type="button"
              class="tombol-ikon sandi__lihat"
              :aria-label="lihatSandi ? 'Sembunyikan kata sandi' : 'Tampilkan kata sandi'"
              @click="lihatSandi = !lihatSandi"
            >
              <EyeOff v-if="lihatSandi" :size="20" />
              <Eye v-else :size="20" />
            </button>
          </div>
          <p v-if="galatIsian.password" id="masuk-sandi-galat" class="isian__galat">{{ galatIsian.password }}</p>
        </div>

        <button type="submit" class="tombol tombol--utama tombol--besar tombol--penuh auth__kirim" :disabled="mengirim">
          {{ mengirim ? 'Memproses…' : 'Masuk' }}
        </button>
      </form>

      <p class="auth__kaki">
        Belum punya akun?
        <RouterLink :to="{ name: 'daftar', query: route.query }">Daftar</RouterLink>
      </p>
    </section>
  </div>
</template>
