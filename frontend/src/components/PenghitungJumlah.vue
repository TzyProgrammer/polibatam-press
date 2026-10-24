<script setup>
import { computed } from 'vue'
import { Minus, Plus } from '@lucide/vue'

// Penghitung jumlah (−, isian angka, +) untuk buku cetak. Nilai baru dikirim lewat update:modelValue;
// induk yang menentukan nilai akhirnya (misalnya setelah disimpan ke server).
// Tombol di batas memakai aria-disabled, bukan disabled, agar fokus papan ketik tidak hilang.
const props = defineProps({
  modelValue: { type: Number, required: true },
  min: { type: Number, default: 1 },
  max: { type: Number, default: 99 },
  // Sedang menyimpan: tombol dan isian tidak menerima perubahan dulu.
  sibuk: { type: Boolean, default: false },
  label: { type: String, default: 'Jumlah' },
})

const emit = defineEmits(['update:modelValue'])

const batasAtas = computed(() => Math.max(props.min, props.max))
const bisaKurang = computed(() => !props.sibuk && props.modelValue > props.min)
const bisaTambah = computed(() => !props.sibuk && props.modelValue < batasAtas.value)

function batasi(nilai) {
  const angka = Number.parseInt(nilai, 10)
  if (Number.isNaN(angka)) return props.modelValue
  return Math.min(batasAtas.value, Math.max(props.min, angka))
}

function kirim(nilai) {
  if (props.sibuk) return
  const hasil = batasi(nilai)
  if (hasil !== props.modelValue) emit('update:modelValue', hasil)
}

function ubahIsian(event) {
  const nilai = event.target.value
  // Tampilkan kembali nilai saat ini; bila perubahan diterima induk, isian ikut diperbarui.
  event.target.value = String(props.modelValue)
  kirim(nilai)
}
</script>

<template>
  <div class="penghitung" role="group" :aria-label="label" :aria-busy="sibuk ? 'true' : undefined">
    <button
      type="button"
      aria-label="Kurangi jumlah"
      :aria-disabled="bisaKurang ? undefined : 'true'"
      @click="bisaKurang && kirim(modelValue - 1)"
    >
      <Minus :size="18" />
    </button>
    <input
      :value="modelValue"
      type="number"
      :min="min"
      :max="batasAtas"
      inputmode="numeric"
      :aria-label="label"
      :readonly="sibuk"
      @change="ubahIsian"
    >
    <button
      type="button"
      aria-label="Tambah jumlah"
      :aria-disabled="bisaTambah ? undefined : 'true'"
      @click="bisaTambah && kirim(modelValue + 1)"
    >
      <Plus :size="18" />
    </button>
  </div>
</template>

<style scoped>
.penghitung {
  display: inline-flex;
  align-items: center;
  overflow: hidden;
  border: 1px solid var(--garis-isian);
  border-radius: var(--radius-kecil);
  background: var(--permukaan);
}

.penghitung button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border: 0;
  background: transparent;
  color: var(--navy);
  cursor: pointer;
}

.penghitung button:hover {
  background: var(--navy-50);
}

.penghitung button[aria-disabled='true'] {
  background: transparent;
  color: var(--garis-isian);
  cursor: not-allowed;
}

.penghitung input {
  width: 56px;
  height: 44px;
  border: 0;
  border-inline: 1px solid var(--garis);
  border-radius: 0;
  background: transparent;
  text-align: center;
  -moz-appearance: textfield;
}

.penghitung input:focus-visible {
  outline-offset: -3px;
}

.penghitung input::-webkit-inner-spin-button,
.penghitung input::-webkit-outer-spin-button {
  margin: 0;
  -webkit-appearance: none;
}

.penghitung[aria-busy='true'] input {
  color: var(--teks-redup);
}
</style>
