<script setup>
import { RouterLink } from 'vue-router'
</script>

<template>
  <div class="wadah halaman">
    <div class="kartu kartu--isi tidak-ditemukan">
      <h1 class="halaman__judul">Halaman tidak ditemukan</h1>
      <p class="halaman__sub">Alamat yang Anda buka tidak ada atau sudah dipindahkan.</p>
      <RouterLink :to="{ name: 'beranda' }" class="tombol tombol--utama">Kembali ke katalog</RouterLink>
    </div>
  </div>
</template>

<style scoped>
.tidak-ditemukan {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
}
</style>
