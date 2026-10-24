<script setup>
import { RouterLink } from 'vue-router'

import { KONTAK } from '../konfigurasi'

const tahun = new Date().getFullYear()
const kontak = [KONTAK.email && `Email ${KONTAK.email}`, KONTAK.whatsapp && `WhatsApp ${KONTAK.whatsapp}`]
  .filter(Boolean)
  .join(' · ')
</script>

<template>
  <footer class="kaki">
    <div class="wadah kaki__baris">
      <div class="kaki__identitas">
        <p class="kaki__nama">Polibatam Press</p>
        <p>Penerbit Politeknik Negeri Batam</p>
        <p v-if="kontak">{{ kontak }}</p>
      </div>
      <nav class="kaki__nav" aria-label="Tautan bawah">
        <RouterLink :to="{ name: 'beranda' }">Katalog</RouterLink>
        <RouterLink :to="{ name: 'koleksi' }">Koleksi</RouterLink>
        <RouterLink :to="{ name: 'pesanan' }">Pesanan</RouterLink>
        <RouterLink :to="{ name: 'isbn' }">Pengajuan ISBN</RouterLink>
      </nav>
    </div>
    <div class="kaki__hak">
      <p class="wadah">© {{ tahun }} Polibatam Press · Politeknik Negeri Batam</p>
    </div>
  </footer>
</template>

<style scoped>
.kaki {
  border-top: 1px solid var(--garis);
  background: var(--permukaan);
  font-size: 0.875rem;
}

.kaki__baris {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 16px 48px;
  padding-block: 28px;
}

.kaki__identitas {
  display: flex;
  flex-direction: column;
  gap: 2px;
  color: var(--teks-redup);
}

.kaki__nama {
  color: var(--navy);
  font-family: var(--font-judul);
  font-size: 1rem;
  font-weight: 700;
}

.kaki__nav {
  display: flex;
  flex-wrap: wrap;
  gap: 0 20px;
}

.kaki__nav a {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  color: var(--teks);
}

.kaki__nav a:hover {
  color: var(--navy);
}

.kaki__hak {
  border-top: 1px solid var(--garis-lembut);
}

.kaki__hak p {
  padding-block: 12px;
  font-size: 0.8125rem;
  color: var(--teks-redup);
}
</style>
