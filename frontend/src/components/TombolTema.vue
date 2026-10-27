<script setup>
import { computed } from 'vue'
import { Monitor, Moon, Sun } from '@lucide/vue'

import { LABEL_TEMA, URUTAN_TEMA, pilihTema, tema, temaBerikutnya } from '../utils/tema'

// bentuk "ikon": satu tombol yang berputar sistem → terang → gelap (header, seperti Django Admin).
// bentuk "pilihan": tiga tombol berdampingan (laci menu ponsel).
defineProps({ bentuk: { type: String, default: 'ikon' } })

const IKON = { sistem: Monitor, terang: Sun, gelap: Moon }
const labelTombol = computed(
  () => `Tema: ${LABEL_TEMA[tema.value]}. Ganti ke ${LABEL_TEMA[temaBerikutnya()]}`,
)
</script>

<template>
  <button
    v-if="bentuk === 'ikon'"
    type="button"
    class="tombol-ikon"
    :aria-label="labelTombol"
    :title="labelTombol"
    @click="pilihTema(temaBerikutnya())"
  >
    <component :is="IKON[tema]" :size="22" />
  </button>
  <div v-else class="tema-pilihan" role="group" aria-label="Tema tampilan">
    <button
      v-for="nama in URUTAN_TEMA"
      :key="nama"
      type="button"
      class="tema-pilihan__tombol"
      :aria-pressed="tema === nama ? 'true' : 'false'"
      @click="pilihTema(nama)"
    >
      <component :is="IKON[nama]" :size="18" />
      {{ LABEL_TEMA[nama] }}
    </button>
  </div>
</template>

<style scoped>
.tema-pilihan {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 4px;
  padding: 4px;
  border: 1px solid var(--garis);
  border-radius: var(--radius);
  background: var(--latar);
}

.tema-pilihan__tombol {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 40px;
  padding: 0 8px;
  border: 0;
  border-radius: var(--radius-kecil);
  background: transparent;
  color: var(--teks-redup);
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
}

.tema-pilihan__tombol:hover {
  color: var(--navy);
}

.tema-pilihan__tombol[aria-pressed='true'] {
  background: var(--permukaan);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.18);
  color: var(--navy);
}
</style>
