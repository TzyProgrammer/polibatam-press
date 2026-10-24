<script setup>
import { ref, watch } from 'vue'
import { BookOpen } from '@lucide/vue'

// Sampul memakai presigned URL (berlaku 1 jam). Bila kosong atau gagal dimuat, tampil pengganti berisi judul.
const props = defineProps({
  src: { type: String, default: '' },
  alt: { type: String, default: '' },
  judul: { type: String, default: '' },
  segera: { type: Boolean, default: false },
})

const gagal = ref(false)
watch(
  () => props.src,
  () => {
    gagal.value = false
  },
)
</script>

<template>
  <div class="sampul">
    <img
      v-if="src && !gagal"
      :src="src"
      :alt="alt"
      :loading="segera ? 'eager' : 'lazy'"
      decoding="async"
      @error="gagal = true"
    >
    <div
      v-else
      class="sampul__pengganti"
      :role="alt ? 'img' : undefined"
      :aria-label="alt || undefined"
      :aria-hidden="alt ? undefined : 'true'"
    >
      <BookOpen :size="32" />
      <span>{{ judul }}</span>
    </div>
  </div>
</template>

<style scoped>
.sampul {
  aspect-ratio: 3 / 4;
  overflow: hidden;
  background: var(--navy-50);
}

.sampul img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.sampul__pengganti {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  height: 100%;
  padding: 16px;
  color: var(--navy);
  font-family: var(--font-judul);
  font-size: 0.875rem;
  font-weight: 600;
  line-height: 1.3;
  text-align: center;
  overflow-wrap: anywhere;
}
</style>
