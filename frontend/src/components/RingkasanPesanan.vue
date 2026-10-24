<script setup>
import { formatRupiah } from '../utils/format'

// Kartu ringkasan di sisi kanan halaman checkout dan pembayaran: daftar produk, rincian biaya, total.
defineProps({
  judul: { type: String, default: 'Ringkasan pesanan' },
  idJudul: { type: String, default: 'judul-ringkasan' },
  // [{ kunci, judul, keterangan, harga }]
  baris: { type: Array, required: true },
  // [{ label, nilai }] — nilai berupa angka (rupiah) atau teks, misalnya "Gratis".
  rincian: { type: Array, default: () => [] },
  total: { type: Number, required: true },
})

function tampil(nilai) {
  return typeof nilai === 'number' ? formatRupiah(nilai) : nilai
}
</script>

<template>
  <aside class="kartu kartu--isi ringkasan" :aria-labelledby="idJudul">
    <div class="ringkasan__kepala">
      <h2 :id="idJudul" class="ringkasan__judul">{{ judul }}</h2>
      <slot name="kepala" />
    </div>
    <ul class="ringkasan__daftar">
      <li v-for="b in baris" :key="b.kunci" class="ringkasan__baris">
        <span class="ringkasan__produk">
          <span class="ringkasan__nama">{{ b.judul }}</span>
          <span class="ringkasan__ket">{{ b.keterangan }}</span>
        </span>
        <span class="ringkasan__harga">{{ formatRupiah(b.harga) }}</span>
      </li>
    </ul>
    <dl v-if="rincian.length" class="ringkasan__rincian">
      <div v-for="r in rincian" :key="r.label">
        <dt>{{ r.label }}</dt>
        <dd>{{ tampil(r.nilai) }}</dd>
      </div>
    </dl>
    <p class="ringkasan__total">
      <span>Total</span>
      <span class="ringkasan__angka">{{ formatRupiah(total) }}</span>
    </p>
    <slot />
  </aside>
</template>

<style scoped>
.ringkasan {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ringkasan__kepala {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 4px 12px;
}

.ringkasan__judul {
  font-size: 1.125rem;
}

.ringkasan__daftar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin: 0;
  padding: 0 0 16px;
  border-bottom: 1px solid var(--garis-lembut);
  list-style: none;
}

.ringkasan__baris {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.ringkasan__produk {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.ringkasan__nama {
  font-weight: 600;
  line-height: 1.4;
  overflow-wrap: anywhere;
}

.ringkasan__ket {
  color: var(--teks-redup);
  font-size: 0.8125rem;
}

.ringkasan__harga {
  flex: none;
  font-weight: 600;
}

.ringkasan__rincian {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0;
}

.ringkasan__rincian div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.ringkasan__rincian dt {
  color: var(--teks-redup);
}

.ringkasan__rincian dd {
  margin: 0;
  text-align: right;
}

.ringkasan__total {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding-top: 16px;
  border-top: 1px solid var(--garis-lembut);
  font-weight: 700;
}

.ringkasan__angka {
  color: var(--navy);
  font-size: 1.375rem;
}
</style>
