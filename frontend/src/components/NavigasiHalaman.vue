<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { ChevronLeft, ChevronRight } from '@lucide/vue'

// Navigasi halaman berupa tautan (bisa dibuka di tab baru dan dibagikan). `tautan(n)` menghasilkan
// lokasi rute untuk halaman n.
const props = defineProps({
  halaman: { type: Number, required: true },
  jumlah: { type: Number, required: true },
  tautan: { type: Function, required: true },
  label: { type: String, default: 'Navigasi halaman' },
})

// Selalu tampil: halaman pertama, terakhir, dan satu halaman di kiri-kanan halaman aktif.
const nomor = computed(() => {
  const terpilih = [1, props.jumlah, props.halaman - 1, props.halaman, props.halaman + 1]
  const urut = [...new Set(terpilih.filter((n) => n >= 1 && n <= props.jumlah))].sort((a, b) => a - b)
  const hasil = []
  urut.forEach((n, i) => {
    if (i && n - urut[i - 1] > 1) hasil.push(null)
    hasil.push(n)
  })
  return hasil
})
</script>

<template>
  <nav v-if="jumlah > 1" class="paginasi" :aria-label="label">
    <RouterLink v-if="halaman > 1" :to="tautan(halaman - 1)" class="paginasi__item" aria-label="Halaman sebelumnya">
      <ChevronLeft :size="20" />
    </RouterLink>
    <span v-else class="paginasi__item is-nonaktif" aria-hidden="true"><ChevronLeft :size="20" /></span>

    <template v-for="(n, i) in nomor" :key="n === null ? `jeda-${i}` : n">
      <span v-if="n === null" class="paginasi__jeda" aria-hidden="true">…</span>
      <RouterLink
        v-else
        :to="tautan(n)"
        class="paginasi__item"
        :class="{ 'is-aktif': n === halaman }"
        :aria-current="n === halaman ? 'page' : undefined"
        :aria-label="`Halaman ${n}`"
      >
        {{ n }}
      </RouterLink>
    </template>

    <RouterLink v-if="halaman < jumlah" :to="tautan(halaman + 1)" class="paginasi__item" aria-label="Halaman berikutnya">
      <ChevronRight :size="20" />
    </RouterLink>
    <span v-else class="paginasi__item is-nonaktif" aria-hidden="true"><ChevronRight :size="20" /></span>
  </nav>
</template>

<style scoped>
.paginasi {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 8px;
}

.paginasi__item {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 44px;
  height: 44px;
  padding: 0 8px;
  border: 1px solid var(--garis-isian);
  border-radius: var(--radius-kecil);
  background: var(--permukaan);
  color: var(--navy);
  font-weight: 600;
  text-decoration: none;
}

a.paginasi__item:hover {
  border-color: var(--navy);
  background: var(--navy-50);
}

.paginasi__item.is-aktif {
  border-color: var(--navy);
  background: var(--navy);
  color: #fff;
}

.paginasi__item.is-nonaktif {
  border-color: var(--garis-lembut);
  color: var(--garis-isian);
}

.paginasi__jeda {
  min-width: 20px;
  color: var(--teks-redup);
  text-align: center;
}
</style>
