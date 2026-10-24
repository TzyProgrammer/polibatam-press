<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import { formatRupiah, labelFormatSingkat } from '../utils/format'
import SampulBuku from './SampulBuku.vue'

const props = defineProps({
  buku: { type: Object, required: true },
})

const format = computed(() => props.buku.produk.map((p) => labelFormatSingkat(p.format)).join(' · '))
</script>

<template>
  <article class="kartu-buku">
    <SampulBuku :src="buku.sampul" :judul="buku.judul" />
    <div class="kartu-buku__isi">
      <h3 class="kartu-buku__judul">
        <RouterLink :to="{ name: 'buku', params: { slug: buku.slug } }" class="kartu-buku__tautan">
          {{ buku.judul }}
        </RouterLink>
      </h3>
      <p class="kartu-buku__penulis">{{ buku.penulis }}</p>
      <p class="kartu-buku__harga">Mulai {{ formatRupiah(buku.harga_mulai) }}</p>
      <p class="kartu-buku__format">{{ format }}</p>
    </div>
  </article>
</template>

<style scoped>
.kartu-buku {
  position: relative;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--garis);
  border-radius: var(--radius);
  background: var(--permukaan);
  transition: border-color 0.15s, box-shadow 0.15s;
}

.kartu-buku:hover {
  border-color: var(--navy);
  box-shadow: var(--bayangan);
}

.kartu-buku:focus-within {
  outline: 3px solid var(--navy);
  outline-offset: 2px;
}

.kartu-buku__isi {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
}

.kartu-buku__judul {
  display: -webkit-box;
  overflow: hidden;
  font-family: var(--font-isi);
  font-size: 0.9375rem;
  font-weight: 600;
  line-height: 1.35;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

/* Seluruh kartu bisa diklik, tetapi nama tautan cukup judul buku. */
.kartu-buku__tautan {
  color: var(--teks);
  text-decoration: none;
}

.kartu-buku__tautan::after {
  content: '';
  position: absolute;
  inset: 0;
}

.kartu-buku__tautan:focus-visible {
  outline: none;
}

.kartu-buku__penulis {
  overflow: hidden;
  font-size: 0.8125rem;
  color: var(--teks-redup);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kartu-buku__harga {
  margin-top: auto;
  padding-top: 4px;
  color: var(--navy);
  font-size: 0.9375rem;
  font-weight: 700;
}

.kartu-buku__format {
  font-size: 0.75rem;
  color: var(--teks-redup);
}
</style>
