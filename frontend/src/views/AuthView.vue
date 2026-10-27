<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import gupoltek from '../assets/gupoltek.jpg'
import logo from '../assets/logo-polibatam-press.jpg'
import tapoltek from '../assets/tapoltek.jpg'
import FormAturUlangSandi from '../components/auth/FormAturUlangSandi.vue'
import FormDaftar from '../components/auth/FormDaftar.vue'
import FormLupaSandi from '../components/auth/FormLupaSandi.vue'
import FormMasuk from '../components/auth/FormMasuk.vue'

// Satu halaman untuk Masuk, Daftar, Lupa kata sandi, dan Atur ulang kata sandi (revisi Tahap R).
// Keempat rute memakai komponen ini sehingga Vue tidak membuatnya ulang saat berpindah rute.
// - Sisi kiri (panel jingga): Masuk, Lupa kata sandi, Atur ulang kata sandi.
// - Sisi kanan (panel biru tua): Daftar.
// Kedua sisi diam di tempat; hanya panel foto yang bergeser menutupi sisi yang tidak dipakai, seperti pintu
// geser. Ke Daftar foto bergerak kanan → kiri, mulai perlahan (ease-in) lalu mendarat lembut; kembali ke
// Masuk foto bergerak kiri → kanan, cepat di awal lalu melambat panjang (ease-out). Formulir lama memudar
// lebih dulu, formulir baru muncul saat sisinya mulai terbuka. Di dalam panel, foto berganti (memudar) dengan
// sedikit efek kedalaman (parallax).
// Pengguna yang memilih kurangi gerakan (prefers-reduced-motion) tidak melihat animasi (styles/dasar.css).
const route = useRoute()

const FORM_KIRI = {
  masuk: FormMasuk,
  'lupa-sandi': FormLupaSandi,
  'atur-ulang-sandi': FormAturUlangSandi,
}
const mode = computed(() => (route.name === 'daftar' || route.name in FORM_KIRI ? route.name : 'masuk'))
const daftar = computed(() => mode.value === 'daftar')

// Pergantian di sisi kiri (Masuk ↔ Lupa ↔ Atur ulang) cukup memudar singkat; perpindahan ke atau dari Daftar
// mengikuti geseran panel foto. Watcher berjalan sebelum render, jadi nama transisi sudah benar saat dipakai.
const modeSebelumnya = ref(null)
watch(mode, (_baru, lama) => {
  modeSebelumnya.value = lama
})
const transisiKiri = computed(() => (daftar.value || modeSebelumnya.value === 'daftar' ? 'auth-sisi' : 'auth-isi'))

const FOTO = {
  masuk: {
    judul: 'Selamat datang kembali',
    teks: 'Buku cetak, ebook, dan audiobook terbitan Polibatam Press dalam satu tempat.',
    kredit: 'Gedung Utama Politeknik Negeri Batam',
  },
  daftar: {
    judul: 'Bergabung dengan Polibatam Press',
    teks: 'Beli buku, simpan ebook dan audiobook di Koleksi, dan ajukan ISBN untuk naskah Anda.',
    kredit: 'Tower A Politeknik Negeri Batam',
  },
}
const foto = computed(() => (daftar.value ? FOTO.daftar : FOTO.masuk))
</script>

<template>
  <div class="wadah halaman">
    <section class="auth-geser" :class="daftar ? 'is-daftar' : 'is-masuk'" :aria-labelledby="`judul-${mode}`">
      <div class="auth-geser__sisi auth-geser__sisi--kiri" :inert="daftar">
        <Transition :name="transisiKiri" mode="out-in">
          <component :is="FORM_KIRI[mode]" v-if="!daftar" :key="mode" />
        </Transition>
      </div>

      <div class="auth-geser__sisi auth-geser__sisi--kanan" :inert="!daftar">
        <Transition name="auth-sisi">
          <FormDaftar v-if="daftar" />
        </Transition>
      </div>

      <div class="auth-geser__foto" aria-hidden="true">
        <div class="auth-geser__bingkai">
          <img :src="gupoltek" alt="" class="auth-geser__gambar" :class="{ 'is-tampil': !daftar }">
          <img :src="tapoltek" alt="" class="auth-geser__gambar" :class="{ 'is-tampil': daftar }">
        </div>
        <div class="auth-geser__tirai" />
        <div class="auth-geser__keterangan">
          <img :src="logo" alt="" width="56" height="56" class="auth-geser__logo">
          <Transition name="auth-kata" mode="out-in">
            <div :key="daftar ? 'daftar' : 'masuk'" class="auth-geser__kata">
              <p class="auth-geser__judul">{{ foto.judul }}</p>
              <p class="auth-geser__teks">{{ foto.teks }}</p>
              <p class="auth-geser__kredit">{{ foto.kredit }}</p>
            </div>
          </Transition>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
/* Warna panel. Teks gelap di atas jingga (5,4:1) dan teks putih di atas biru tua (11,5:1);
   di tema gelap jingga diganti cokelat-jingga tua bertulisan terang. */
.auth-geser {
  --panel-masuk: #f2692a;
  --panel-masuk-teks: #1a1f2b;
  --panel-daftar: #1e376c;
  --panel-daftar-teks: #ffffff;
  /* Geseran panel foto. Ke Daftar: perlahan di awal, mendarat lembut. Ke Masuk: cepat di awal, melambat panjang. */
  --durasi-geser: 0.9s;
  --kurva-ke-daftar: cubic-bezier(0.65, 0, 0.35, 1);
  --kurva-ke-masuk: cubic-bezier(0.22, 1, 0.36, 1);

  position: relative;
  display: grid;
  grid-template-columns: 1fr 1fr;
  /* Cukup untuk formulir Daftar (yang terpanjang) pada lebar 1024 px ke atas, agar tinggi kartu tidak
     berubah saat berganti formulir. */
  min-height: 800px;
  overflow: hidden;
  border-radius: 16px;
  background: var(--latar-merek);
  box-shadow: var(--bayangan);
}

:root[data-tema='gelap'] .auth-geser {
  --panel-masuk: #6b2c10;
  --panel-masuk-teks: #fff3eb;
  --panel-daftar: #14264d;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-tema]) .auth-geser {
    --panel-masuk: #6b2c10;
    --panel-masuk-teks: #fff3eb;
    --panel-daftar: #14264d;
  }
}

.auth-geser__sisi {
  display: flex;
  grid-row: 1;
  flex-direction: column;
  justify-content: center;
  min-width: 0;
  padding: 40px 48px;
}

.auth-geser__sisi--kiri {
  grid-column: 1;
  background: var(--panel-masuk);
  color: var(--panel-masuk-teks);
}

.auth-geser__sisi--kanan {
  grid-column: 2;
  background: var(--panel-daftar);
  color: var(--panel-daftar-teks);
}

/* Panel foto: satu-satunya bagian yang bergerak. Hanya transform yang dianimasikan (dikerjakan GPU), jadi
   tata letak halaman tidak dihitung ulang selama geseran. */
.auth-geser__foto {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 50%;
  z-index: 2;
  width: 50%;
  overflow: hidden;
  background: var(--latar-merek);
  box-shadow: 0 0 48px rgba(8, 16, 36, 0.35);
  transition: transform var(--durasi-geser) var(--kurva-ke-masuk);
  will-change: transform;
}

.is-daftar .auth-geser__foto {
  transform: translateX(-100%);
  transition-timing-function: var(--kurva-ke-daftar);
}

/* Lapisan foto sedikit lebih lebar dari panel dan bergeser berlawanan arah (parallax), sehingga foto
   terasa lebih jauh daripada bingkainya. */
.auth-geser__bingkai {
  position: absolute;
  inset: 0 -8%;
  transform: translateX(-4%);
  transition: transform var(--durasi-geser) var(--kurva-ke-masuk);
}

.is-daftar .auth-geser__bingkai {
  transform: translateX(4%);
  transition-timing-function: var(--kurva-ke-daftar);
}

.auth-geser__gambar {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0;
  transform: scale(1.08);
  transition:
    opacity 0.6s ease 0.15s,
    transform 1.4s cubic-bezier(0.22, 1, 0.36, 1);
}

.auth-geser__gambar.is-tampil {
  opacity: 1;
  transform: scale(1);
}

.auth-geser__tirai {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(20, 38, 77, 0.1) 0%, rgba(20, 38, 77, 0.35) 45%, rgba(20, 38, 77, 0.88) 100%);
}

.auth-geser__keterangan {
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 40px;
  color: #fff;
}

.auth-geser__logo {
  width: 56px;
  height: 56px;
  border-radius: 10px;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.3);
}

.auth-geser__kata {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.auth-geser__judul {
  font-family: var(--font-judul);
  font-size: 1.625rem;
  font-weight: 700;
  line-height: 1.25;
}

.auth-geser__teks {
  max-width: 420px;
  color: #e6ebf5;
}

.auth-geser__kredit {
  margin-top: 6px;
  color: #c9d3e6;
  font-size: 0.8125rem;
}

/* Isi formulir di atas panel berwarna */
.auth-geser :deep(.auth-form) {
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 100%;
  max-width: 460px;
  margin: 0 auto;
}

.auth-geser__sisi--kanan :deep(.auth-form) {
  max-width: 520px;
}

.auth-geser :deep(.auth-form__kepala) {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.auth-geser :deep(.auth-form__judul) {
  color: inherit;
  font-size: 1.875rem;
}

.auth-geser :deep(.auth-form__sub),
.auth-geser :deep(.isian__petunjuk) {
  color: inherit;
  opacity: 0.88;
}

.auth-geser :deep(.isian__kontrol) {
  border-color: transparent;
  color: var(--teks);
}

.auth-geser :deep(.isian__galat) {
  align-self: flex-start;
  padding: 2px 8px;
  border-radius: 6px;
  background: var(--permukaan);
  color: var(--galat);
}

.auth-geser :deep(.formulir--rapat) {
  gap: 12px;
}

.auth-geser :deep(.baris-isian > .isian) {
  flex-basis: 180px;
}

.auth-geser :deep(.auth-form__lupa) {
  align-self: flex-end;
  margin-top: -6px;
  color: inherit;
  font-size: 0.875rem;
  font-weight: 700;
}

.auth-geser :deep(.auth-form__kirim) {
  margin-top: 4px;
}

.auth-geser :deep(.auth-form__kaki) {
  padding-top: 16px;
  border-top: 1px solid currentColor;
  border-top-color: color-mix(in srgb, currentColor 30%, transparent);
}

.auth-geser :deep(.auth-form__kaki a) {
  color: inherit;
  font-weight: 700;
}

.auth-geser :deep(.auth-form__memuat) {
  opacity: 0.88;
}

/* Panel Daftar (biru tua): tombol utama jingga bertulisan gelap agar tetap menonjol, garis fokus putih. */
.auth-geser__sisi--kanan :deep(.tombol--utama) {
  background: var(--jingga);
  color: var(--teks-di-jingga);
}

.auth-geser__sisi--kanan :deep(.tombol--utama:hover) {
  background: #f58a55;
  color: var(--teks-di-jingga);
}

.auth-geser__sisi--kanan :deep(:focus-visible),
.auth-geser__sisi--kanan :deep(.isian__kontrol:focus-visible) {
  outline-color: #fff;
}

/* Pergantian formulir di sisi yang sama (Masuk ↔ Lupa ↔ Atur ulang): memudar sambil sedikit bergeser. */
.auth-isi-enter-active,
.auth-isi-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.auth-isi-enter-from,
.auth-isi-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

/* Pergantian sisi (Masuk ↔ Daftar): formulir lama memudar cepat saat panel foto mulai menutupinya; formulir
   baru muncul setelah sisinya mulai terbuka, sedikit bergeser searah gerakan panel foto. */
.auth-sisi-leave-active {
  transition: opacity 0.25s ease, transform 0.35s ease;
}

.auth-sisi-enter-active {
  transition:
    opacity 0.5s ease 0.3s,
    transform 0.6s cubic-bezier(0.22, 1, 0.36, 1) 0.3s;
}

/* Kembali ke Masuk: panel foto cepat di awal, jadi sisi kiri lebih cepat terbuka. */
.is-masuk .auth-sisi-enter-active {
  transition-delay: 0.15s;
}

.auth-geser__sisi--kiri .auth-sisi-leave-to,
.auth-geser__sisi--kiri .auth-sisi-enter-from {
  opacity: 0;
  transform: translateX(-24px);
}

.auth-geser__sisi--kanan .auth-sisi-leave-to,
.auth-geser__sisi--kanan .auth-sisi-enter-from {
  opacity: 0;
  transform: translateX(24px);
}

/* Keterangan foto: keluar cepat, masuk saat panel foto hampir mendarat. */
.auth-kata-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.auth-kata-enter-active {
  transition: opacity 0.45s ease 0.25s, transform 0.45s ease 0.25s;
}

.auth-kata-enter-from,
.auth-kata-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

@media (max-width: 1023px) {
  /* Ponsel dan tablet: foto menjadi pita di atas formulir, tanpa geseran; hanya sisi yang aktif ditampilkan.
     Di bawah 1024 px kolom terlalu sempit sehingga formulir Daftar memanjang dan tinggi kartu akan melompat. */
  .auth-geser {
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .is-daftar .auth-geser__sisi--kiri,
  .is-masuk .auth-geser__sisi--kanan {
    display: none;
  }

  .auth-geser__foto {
    position: relative;
    left: auto;
    order: -1;
    width: auto;
    height: 168px;
    flex: none;
    box-shadow: none;
    transform: none !important;
  }

  .auth-geser__bingkai {
    inset: 0;
    transform: none !important;
  }

  .auth-geser__sisi {
    padding: 28px 20px 32px;
  }

  .auth-sisi-enter-active,
  .is-masuk .auth-sisi-enter-active {
    transition-delay: 0s;
  }

  .auth-geser__keterangan {
    flex-direction: row;
    align-items: center;
    gap: 12px;
    padding: 20px;
  }

  .auth-geser__logo {
    width: 44px;
    height: 44px;
  }

  .auth-geser__judul {
    font-size: 1.125rem;
  }

  .auth-geser__teks,
  .auth-geser__kredit {
    display: none;
  }

  .auth-geser :deep(.auth-form__judul) {
    font-size: 1.5rem;
  }
}

@media (max-width: 719px) {
  .halaman:has(.auth-geser) {
    padding-top: 16px;
  }
}
</style>
