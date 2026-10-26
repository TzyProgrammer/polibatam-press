<script setup>
import { computed, watch } from 'vue'
import { RouterView, useRoute } from 'vue-router'

import DaftarPesan from './components/DaftarPesan.vue'
import SiteFooter from './components/SiteFooter.vue'
import SiteHeader from './components/SiteHeader.vue'
import { useAuthStore } from './stores/auth'
import { useKeranjangStore } from './stores/keranjang'
import { useNotifikasiStore } from './stores/notifikasi'

const auth = useAuthStore()
const keranjang = useKeranjangStore()
const notifikasi = useNotifikasiStore()
const route = useRoute()

// Halaman layar penuh (pembaca ebook) memakai bilah sendiri, tanpa header dan footer situs.
const tanpaKerangka = computed(() => Boolean(route.meta.tanpaKerangka))

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
  <SiteHeader v-if="!tanpaKerangka" />
  <main id="konten" class="konten" tabindex="-1">
    <RouterView />
  </main>
  <SiteFooter v-if="!tanpaKerangka" />
  <DaftarPesan />
</template>
