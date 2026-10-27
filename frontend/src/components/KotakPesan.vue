<script setup>
import { computed } from 'vue'
import { CircleAlert, CircleCheck, Info } from '@lucide/vue'

const props = defineProps({
  // galat | sukses | info
  jenis: { type: String, default: 'info' },
})

const ikon = computed(() => ({ galat: CircleAlert, sukses: CircleCheck })[props.jenis] || Info)
</script>

<template>
  <div class="kotak-pesan" :class="`kotak-pesan--${jenis}`" :role="jenis === 'galat' ? 'alert' : 'status'">
    <component :is="ikon" :size="20" class="kotak-pesan__ikon" />
    <div class="kotak-pesan__isi">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.kotak-pesan {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 14px;
  border: 1px solid var(--navy-100);
  border-radius: var(--radius);
  background: var(--navy-50);
  color: var(--teks);
  font-size: 0.9375rem;
  line-height: 1.5;
}

.kotak-pesan__ikon {
  flex: none;
  margin-top: 1px;
  color: var(--navy);
}

.kotak-pesan__isi {
  display: flex;
  flex: 1;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
}

.kotak-pesan--galat {
  border-color: var(--galat-garis);
  background: var(--galat-50);
}

.kotak-pesan--galat .kotak-pesan__ikon {
  color: var(--galat);
}

.kotak-pesan--sukses {
  border-color: var(--sukses-garis);
  background: var(--sukses-50);
}

.kotak-pesan--sukses .kotak-pesan__ikon {
  color: var(--sukses);
}
</style>
