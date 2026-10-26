<script setup>
import { RouterLink } from 'vue-router'
import { BookOpen, FileText, Info, ReceiptText } from '@lucide/vue'

import { formatTanggalJam, formatWaktuRelatif } from '../utils/format'
import { tujuanAman } from '../utils/navigasi'

// Daftar notifikasi. Notifikasi bertautan (path halaman frontend dari backend, misalnya /pesanan/<nomor>)
// menjadi tautan; yang lain menjadi tombol. Memilih notifikasi menandainya dibaca (event "pilih").
defineProps({
  item: { type: Array, required: true },
  ringkas: { type: Boolean, default: false },
})
const emit = defineEmits(['pilih'])

const IKON = { pesanan: ReceiptText, konten: BookOpen, isbn: FileText }

function tautan(n) {
  return n.tautan ? tujuanAman(n.tautan, '') : ''
}
</script>

<template>
  <ul class="notif-daftar" :class="{ 'notif-daftar--ringkas': ringkas }">
    <li v-for="n in item" :key="n.id" class="notif-daftar__baris" :class="{ 'is-baru': !n.dibaca }">
      <component
        :is="tautan(n) ? RouterLink : 'button'"
        v-bind="tautan(n) ? { to: tautan(n) } : { type: 'button' }"
        class="notif-daftar__isi"
        @click="emit('pilih', n)"
      >
        <span class="notif-daftar__ikon" aria-hidden="true">
          <component :is="IKON[n.kategori] || Info" :size="18" />
        </span>
        <span class="notif-daftar__teks">
          <span class="notif-daftar__judul">
            {{ n.judul }}<span v-if="!n.dibaca" class="sr-only">, belum dibaca</span>
          </span>
          <span class="notif-daftar__pesan">{{ n.pesan }}</span>
          <span class="notif-daftar__meta">
            {{ n.kategori_label }} ·
            <time :datetime="n.dibuat" :title="formatTanggalJam(n.dibuat)">{{ formatWaktuRelatif(n.dibuat) }}</time>
          </span>
        </span>
        <span v-if="!n.dibaca" class="notif-daftar__titik" aria-hidden="true" />
      </component>
    </li>
  </ul>
</template>

<style scoped>
.notif-daftar {
  margin: 0;
  padding: 0;
  list-style: none;
}

.notif-daftar__baris + .notif-daftar__baris {
  border-top: 1px solid var(--garis-lembut);
}

.notif-daftar__isi {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  width: 100%;
  padding: 14px 16px;
  border: 0;
  background: transparent;
  color: var(--teks);
  font: inherit;
  text-align: left;
  text-decoration: none;
  cursor: pointer;
}

.is-baru .notif-daftar__isi {
  background: var(--biru-50);
}

.notif-daftar__isi:hover {
  background: var(--navy-50);
  color: var(--teks);
}

.notif-daftar__isi:focus-visible {
  outline-offset: -3px;
}

.notif-daftar__ikon {
  display: inline-flex;
  flex: none;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--permukaan);
  color: var(--navy);
  box-shadow: inset 0 0 0 1px var(--garis);
}

.notif-daftar__teks {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.notif-daftar__judul {
  font-weight: 700;
  line-height: 1.35;
}

.notif-daftar__pesan {
  color: var(--teks);
  font-size: 0.875rem;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.notif-daftar--ringkas .notif-daftar__pesan {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.notif-daftar__meta {
  color: var(--teks-redup);
  font-size: 0.8125rem;
}

.notif-daftar__titik {
  flex: none;
  width: 10px;
  height: 10px;
  margin-top: 6px;
  border-radius: 50%;
  background: var(--jingga);
}
</style>
