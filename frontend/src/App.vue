<script setup>
import { watch } from 'vue'
import { RouterView } from 'vue-router'

import DaftarPesan from './components/DaftarPesan.vue'
import SiteFooter from './components/SiteFooter.vue'
import SiteHeader from './components/SiteHeader.vue'
import { useAuthStore } from './stores/auth'
import { useKeranjangStore } from './stores/keranjang'
import { useNotifikasiStore } from './stores/notifikasi'

const auth = useAuthStore()
const keranjang = useKeranjangStore()
const notifikasi = useNotifikasiStore()

// Lencana keranjang dan notifikasi hanya dimuat selama pengguna masuk.
watch(
  () => auth.sudahMasuk,
  (masuk) => {
    if (masuk) {
      keranjang.muat()
      notifikasi.mulai()
    } else {
      keranjang.kosongkan()
      notifikasi.kosongkan()
    }
  },
  { immediate: true },
)
</script>

<template>
  <a href="#konten" class="lewati">Lewati ke konten utama</a>
  <SiteHeader />
  <main id="konten" class="konten" tabindex="-1">
    <RouterView />
  </main>
  <SiteFooter />
  <DaftarPesan />
</template>
