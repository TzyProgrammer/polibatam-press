<script setup>
import { computed } from 'vue'
import { Check } from '@lucide/vue'

// Penanda langkah pembelian: Keranjang → Pengiriman (Konfirmasi untuk pesanan digital) → Pembayaran.
// Hanya penanda, bukan navigasi.
const props = defineProps({
  aktif: { type: Number, required: true },
  tanpaPengiriman: { type: Boolean, default: false },
})

const daftar = computed(() => ['Keranjang', props.tanpaPengiriman ? 'Konfirmasi' : 'Pengiriman', 'Pembayaran'])

function keadaan(nomor) {
  if (nomor < props.aktif) return 'selesai'
  return nomor === props.aktif ? 'aktif' : 'nanti'
}
</script>

<template>
  <ol class="langkah" aria-label="Langkah pembelian">
    <li
      v-for="(nama, i) in daftar"
      :key="i"
      class="langkah__item"
      :class="`is-${keadaan(i + 1)}`"
      :aria-current="keadaan(i + 1) === 'aktif' ? 'step' : undefined"
    >
      <span class="langkah__tanda" aria-hidden="true">
        <Check v-if="keadaan(i + 1) === 'selesai'" :size="16" :stroke-width="3" />
        <template v-else>{{ i + 1 }}</template>
      </span>
      <span class="langkah__nama">{{ nama }}</span>
      <span v-if="keadaan(i + 1) === 'selesai'" class="sr-only">(selesai)</span>
    </li>
  </ol>
</template>

<style scoped>
.langkah {
  display: flex;
  align-items: center;
  margin: 0 0 24px;
  padding: 0;
  list-style: none;
}

.langkah__item {
  display: flex;
  flex: none;
  align-items: center;
  gap: 8px;
  color: var(--teks-redup);
  font-size: 0.9375rem;
  font-weight: 600;
}

.langkah__item:not(:last-child) {
  flex: 1 1 auto;
}

/* Garis penghubung ke langkah berikutnya; biru tua bila langkah ini sudah selesai. */
.langkah__item:not(:last-child)::after {
  content: '';
  flex: 1 1 auto;
  min-width: 16px;
  height: 2px;
  margin-inline: 4px 12px;
  border-radius: 1px;
  background: var(--garis);
}

.langkah__item.is-selesai::after {
  background: var(--isi-utama);
}

.langkah__tanda {
  display: inline-flex;
  flex: none;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 2px solid var(--garis-isian);
  border-radius: 50%;
  background: var(--permukaan);
  font-size: 0.8125rem;
  font-weight: 700;
}

.is-selesai .langkah__tanda,
.is-aktif .langkah__tanda {
  border-color: var(--navy);
  background: var(--isi-utama);
  color: #fff;
}

.is-selesai,
.is-aktif {
  color: var(--navy);
}

.langkah__nama {
  white-space: nowrap;
}

/* Ponsel: label di bawah lingkaran, tiga kolom sama lebar. */
@media (max-width: 719px) {
  .langkah {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    align-items: start;
  }

  .langkah__item,
  .langkah__item:not(:last-child) {
    position: relative;
    flex-direction: column;
    gap: 4px;
    font-size: 0.8125rem;
    text-align: center;
  }

  .langkah__item:not(:last-child)::after {
    display: none;
  }

  .langkah__item:not(:first-child)::before {
    content: '';
    position: absolute;
    top: 13px;
    right: calc(50% + 20px);
    left: calc(-50% + 20px);
    height: 2px;
    border-radius: 1px;
    background: var(--garis);
  }

  .langkah__item.is-selesai::before,
  .langkah__item.is-aktif::before {
    background: var(--isi-utama);
  }

  .langkah__nama {
    white-space: normal;
  }
}
</style>
