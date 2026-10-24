<script setup>
import { RouterLink, useRoute } from 'vue-router'

// Pengganti sementara untuk halaman yang dibuat di tahap berikutnya (H2–H4).
const route = useRoute()
</script>

<template>
  <div class="wadah halaman">
    <div class="kartu kartu--isi segera">
      <h1 class="halaman__judul">{{ route.meta.judul }}</h1>
      <p class="halaman__sub">Halaman ini sedang dibangun dan tersedia pada Tahap {{ route.meta.tahap }}.</p>
      <RouterLink :to="{ name: 'beranda' }" class="tombol tombol--utama">Kembali ke katalog</RouterLink>
    </div>
  </div>
</template>

<style scoped>
.segera {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
}
</style>
