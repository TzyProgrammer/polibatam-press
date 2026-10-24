<script setup>
import { RouterLink } from 'vue-router'
import { X } from '@lucide/vue'

import { usePesanStore } from '../stores/pesan'

const pesan = usePesanStore()
</script>

<template>
  <div class="daftar-pesan" aria-live="polite">
    <div v-for="p in pesan.daftar" :key="p.id" class="pesan" :class="`pesan--${p.jenis}`">
      <div class="pesan__isi">
        <p class="pesan__teks">{{ p.teks }}</p>
        <RouterLink v-if="p.tautan" :to="p.tautan.to" class="pesan__tautan" @click="pesan.tutup(p.id)">
          {{ p.tautan.label }}
        </RouterLink>
      </div>
      <button type="button" class="tombol-ikon pesan__tutup" aria-label="Tutup pesan" @click="pesan.tutup(p.id)">
        <X :size="18" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.daftar-pesan {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 50;
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: min(400px, calc(100vw - 32px));
}

.pesan {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 6px 10px 16px;
  border-left: 4px solid var(--biru);
  border-radius: var(--radius);
  background: var(--navy-900);
  color: #fff;
  box-shadow: var(--bayangan);
}

.pesan--sukses {
  border-left-color: #75e0a7;
}

.pesan--galat {
  border-left-color: var(--jingga);
}

.pesan__isi {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  min-width: 0;
  padding-top: 2px;
}

.pesan__teks {
  font-size: 0.9375rem;
  line-height: 1.45;
}

.pesan__tautan {
  display: inline-flex;
  align-items: center;
  min-height: 36px;
  color: #fff;
  font-weight: 700;
}

.pesan__tautan:hover {
  color: var(--biru);
}

.pesan__tutup {
  flex: none;
  width: 36px;
  height: 36px;
  color: #fff;
}

.pesan__tutup:hover {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
}

@media (max-width: 719px) {
  .daftar-pesan {
    right: 16px;
    bottom: 16px;
  }
}
</style>
