<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { X } from '@lucide/vue'

// Modal konfirmasi berbasis <dialog>: fokus terkunci di dalam modal, Escape atau tombol × berarti batal.
// emit "ya" / "tidak" untuk dua pilihan jawaban, "batal" bila modal ditutup tanpa memilih.
const props = defineProps({
  buka: { type: Boolean, default: false },
  judul: { type: String, required: true },
  labelYa: { type: String, default: 'Ya' },
  labelTidak: { type: String, default: 'Tidak' },
})
const emit = defineEmits(['ya', 'tidak', 'batal'])

const dialog = ref(null)
const tombolTidak = ref(null)
const idJudul = `modal-judul-${Math.random().toString(36).slice(2, 8)}`

watch(
  () => props.buka,
  async (buka) => {
    await nextTick()
    const el = dialog.value
    if (!el) return
    if (buka && !el.open) {
      el.showModal()
      tombolTidak.value?.focus()
    } else if (!buka && el.open) {
      el.close()
    }
  },
)

onBeforeUnmount(() => {
  if (dialog.value?.open) dialog.value.close()
})

function batal(event) {
  event?.preventDefault()
  emit('batal')
}

// Klik di luar kotak (pada latar dialog) juga berarti batal.
function klik(event) {
  if (event.target === dialog.value) emit('batal')
}
</script>

<template>
  <dialog ref="dialog" class="modal" :aria-labelledby="idJudul" @cancel="batal" @click="klik">
    <div class="modal__isi">
      <div class="modal__kepala">
        <h2 :id="idJudul" class="modal__judul">{{ judul }}</h2>
        <button type="button" class="tombol-ikon modal__tutup" aria-label="Tutup" @click="batal">
          <X :size="22" />
        </button>
      </div>
      <div class="modal__pesan">
        <slot />
      </div>
      <div class="modal__aksi">
        <button ref="tombolTidak" type="button" class="tombol tombol--sekunder" @click="emit('tidak')">
          {{ labelTidak }}
        </button>
        <button type="button" class="tombol tombol--utama" @click="emit('ya')">{{ labelYa }}</button>
      </div>
    </div>
  </dialog>
</template>

<style scoped>
.modal {
  width: min(520px, calc(100vw - 32px));
  max-width: none;
  padding: 0;
  border: 1px solid var(--garis);
  border-radius: var(--radius-besar);
  background: var(--permukaan);
  color: var(--teks);
  box-shadow: var(--bayangan);
}

.modal::backdrop {
  background: var(--tirai);
}

.modal__isi {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px 24px 24px;
}

.modal__kepala {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.modal__judul {
  padding-top: 8px;
  font-size: 1.25rem;
}

.modal__tutup {
  flex: none;
  margin: 0 -10px 0 0;
}

.modal__pesan {
  display: flex;
  flex-direction: column;
  gap: 12px;
  line-height: 1.55;
}

.modal__aksi {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

@media (max-width: 479px) {
  .modal__aksi {
    flex-direction: column-reverse;
  }

  .modal__aksi .tombol {
    width: 100%;
  }
}
</style>
