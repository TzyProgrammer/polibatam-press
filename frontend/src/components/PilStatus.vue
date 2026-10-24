<script setup>
import { computed } from 'vue'

// Label status pesanan. Warna hanya penegas; teks label selalu tertulis.
const props = defineProps({
  // pembayaran: menunggu | lunas | kedaluwarsa | dibatalkan | gagal
  // pengiriman: menunggu | diproses | dikirim | siap_diambil | selesai | tidak_ada
  jenis: { type: String, default: 'pembayaran' },
  status: { type: String, required: true },
  label: { type: String, required: true },
})

const gaya = computed(() => {
  if (props.jenis === 'pengiriman') {
    if (props.status === 'selesai') return 'selesai'
    return ['diproses', 'dikirim', 'siap_diambil'].includes(props.status) ? 'jalan' : 'tutup'
  }
  return { menunggu: 'menunggu', lunas: 'selesai' }[props.status] || 'tutup'
})
</script>

<template>
  <span class="pil-status" :class="`pil-status--${gaya}`">{{ label }}</span>
</template>

<style scoped>
.pil-status {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 2px 12px;
  border: 1px solid var(--garis);
  border-radius: 999px;
  background: #eef1f5;
  color: var(--teks-redup);
  font-size: 0.8125rem;
  font-weight: 600;
  line-height: 1.3;
  white-space: nowrap;
}

/* Menunggu pembayaran: garis putus-putus jingga, teks gelap (bukan teks putih di atas jingga). */
.pil-status--menunggu {
  border-style: dashed;
  border-color: var(--jingga);
  background: var(--jingga-50);
  color: var(--teks);
}

.pil-status--selesai {
  border-color: #abefc6;
  background: var(--sukses-50);
  color: var(--sukses);
}

.pil-status--jalan {
  border-color: var(--navy-100);
  background: var(--navy-50);
  color: var(--navy);
}
</style>
