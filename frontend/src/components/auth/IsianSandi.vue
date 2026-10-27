<script setup>
import { ref } from 'vue'
import { Eye, EyeOff } from '@lucide/vue'

// Isian kata sandi dengan tombol tampilkan/sembunyikan, dipakai halaman Masuk, Daftar, atur ulang, dan Profil.
const model = defineModel({ type: String, default: '' })
defineProps({
  id: { type: String, required: true },
  label: { type: String, required: true },
  autocomplete: { type: String, default: 'current-password' },
  galat: { type: String, default: '' },
  petunjuk: { type: String, default: '' },
})
const lihat = ref(false)
</script>

<template>
  <div class="isian">
    <label :for="id" class="isian__label">{{ label }}</label>
    <div class="sandi">
      <input
        :id="id"
        v-model="model"
        :type="lihat ? 'text' : 'password'"
        class="isian__kontrol"
        :autocomplete="autocomplete"
        :aria-invalid="galat ? 'true' : undefined"
        :aria-describedby="galat ? `${id}-galat` : petunjuk ? `${id}-petunjuk` : undefined"
      >
      <button
        type="button"
        class="tombol-ikon sandi__lihat"
        :aria-label="lihat ? 'Sembunyikan kata sandi' : 'Tampilkan kata sandi'"
        @click="lihat = !lihat"
      >
        <EyeOff v-if="lihat" :size="20" />
        <Eye v-else :size="20" />
      </button>
    </div>
    <p v-if="galat" :id="`${id}-galat`" class="isian__galat">{{ galat }}</p>
    <p v-else-if="petunjuk" :id="`${id}-petunjuk`" class="isian__petunjuk">{{ petunjuk }}</p>
  </div>
</template>
