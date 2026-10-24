<script setup>
import { computed, reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { BookOpen, FileText, LogOut, ReceiptText } from '@lucide/vue'

import KotakPesan from '../components/KotakPesan.vue'
import { useAuthStore } from '../stores/auth'
import { usePesanStore } from '../stores/pesan'

const auth = useAuthStore()
const pesan = usePesanStore()
const router = useRouter()

const isian = reactive({
  nama_lengkap: auth.pengguna?.nama_lengkap || '',
  no_telepon: auth.pengguna?.no_telepon || '',
  alamat: auth.pengguna?.alamat || '',
})
const galat = ref('')
const galatIsian = ref({})
const berhasil = ref('')
const menyimpan = ref(false)

const peran = computed(() => (auth.pengguna?.role === 'admin' ? 'Admin' : 'Pembeli'))

async function simpan() {
  galat.value = ''
  galatIsian.value = {}
  berhasil.value = ''
  menyimpan.value = true
  try {
    await auth.perbaruiProfil({ ...isian })
    berhasil.value = 'Perubahan profil disimpan.'
  } catch (e) {
    galatIsian.value = e.isian
    galat.value = Object.keys(e.isian).length ? '' : e.detail
  } finally {
    menyimpan.value = false
  }
}

async function keluar() {
  await auth.keluar()
  pesan.tampilkan('Anda sudah keluar.', { jenis: 'info' })
  router.push({ name: 'beranda' })
}

function atributIsian(nama) {
  return galatIsian.value[nama] ? { 'aria-invalid': 'true', 'aria-describedby': `profil-${nama}-galat` } : {}
}
</script>

<template>
  <div class="wadah halaman">
    <div class="halaman__kepala">
      <h1 class="halaman__judul">Profil</h1>
      <p class="halaman__sub">Nama dan telepon di sini dipakai sebagai data penerima saat checkout.</p>
    </div>

    <div class="profil">
      <section class="kartu kartu--isi profil__data" aria-labelledby="judul-data">
        <h2 id="judul-data" class="profil__subjudul">Data akun</h2>
        <KotakPesan v-if="berhasil" jenis="sukses">{{ berhasil }}</KotakPesan>
        <KotakPesan v-if="galat" jenis="galat">{{ galat }}</KotakPesan>
        <form class="formulir" novalidate @submit.prevent="simpan">
          <div class="isian">
            <label for="profil-email" class="isian__label">Email</label>
            <input
              id="profil-email"
              :value="auth.pengguna?.email"
              type="email"
              class="isian__kontrol"
              readonly
              aria-describedby="profil-email-petunjuk"
            >
            <p id="profil-email-petunjuk" class="isian__petunjuk">Email dipakai untuk masuk dan tidak bisa diubah.</p>
          </div>
          <div class="baris-isian">
            <div class="isian">
              <label for="profil-nama" class="isian__label">Nama lengkap</label>
              <input
                id="profil-nama"
                v-model="isian.nama_lengkap"
                type="text"
                class="isian__kontrol"
                autocomplete="name"
                v-bind="atributIsian('nama_lengkap')"
              >
              <p v-if="galatIsian.nama_lengkap" id="profil-nama_lengkap-galat" class="isian__galat">{{ galatIsian.nama_lengkap }}</p>
            </div>
            <div class="isian">
              <label for="profil-telepon" class="isian__label">Nomor telepon</label>
              <input
                id="profil-telepon"
                v-model="isian.no_telepon"
                type="tel"
                class="isian__kontrol"
                autocomplete="tel"
                v-bind="atributIsian('no_telepon')"
              >
              <p v-if="galatIsian.no_telepon" id="profil-no_telepon-galat" class="isian__galat">{{ galatIsian.no_telepon }}</p>
              <p v-else class="isian__petunjuk">Contoh: 0812-3456-7890</p>
            </div>
          </div>
          <div class="isian">
            <label for="profil-alamat" class="isian__label">Alamat</label>
            <textarea
              id="profil-alamat"
              v-model="isian.alamat"
              rows="3"
              class="isian__kontrol"
              autocomplete="street-address"
              v-bind="atributIsian('alamat')"
            />
            <p v-if="galatIsian.alamat" id="profil-alamat-galat" class="isian__galat">{{ galatIsian.alamat }}</p>
          </div>
          <div>
            <button type="submit" class="tombol tombol--utama tombol--besar" :disabled="menyimpan">
              {{ menyimpan ? 'Menyimpan…' : 'Simpan perubahan' }}
            </button>
          </div>
        </form>
      </section>

      <aside class="kartu kartu--isi profil__akun" aria-labelledby="judul-akun">
        <div class="profil__identitas">
          <span class="profil__avatar" aria-hidden="true">{{ auth.inisial }}</span>
          <div class="profil__nama-wadah">
            <h2 id="judul-akun" class="profil__nama">{{ auth.pengguna?.nama_lengkap }}</h2>
            <p class="profil__email">{{ auth.pengguna?.email }}</p>
            <span class="profil__peran">{{ peran }}</span>
          </div>
        </div>
        <nav class="profil__menu" aria-label="Menu akun">
          <RouterLink :to="{ name: 'pesanan' }"><ReceiptText :size="20" />Pesanan saya</RouterLink>
          <RouterLink :to="{ name: 'koleksi' }"><BookOpen :size="20" />Koleksi</RouterLink>
          <RouterLink :to="{ name: 'isbn' }"><FileText :size="20" />Pengajuan ISBN</RouterLink>
        </nav>
        <button type="button" class="tombol tombol--sekunder tombol--penuh" @click="keluar">
          <LogOut :size="20" />
          Keluar
        </button>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.profil {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 24px;
}

.profil__data {
  display: flex;
  flex: 2 1 560px;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.profil__subjudul {
  font-size: 1.25rem;
}

.profil__akun {
  display: flex;
  flex: 1 1 300px;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.profil__identitas {
  display: flex;
  align-items: center;
  gap: 14px;
}

.profil__avatar {
  display: inline-flex;
  flex: none;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: var(--navy);
  color: #fff;
  font-size: 1.25rem;
  font-weight: 700;
}

.profil__nama-wadah {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.profil__nama {
  font-size: 1.125rem;
  overflow-wrap: anywhere;
}

.profil__email {
  color: var(--teks-redup);
  font-size: 0.875rem;
  overflow-wrap: anywhere;
}

.profil__peran {
  align-self: flex-start;
  margin-top: 4px;
  padding: 2px 10px;
  border-radius: 999px;
  background: var(--biru-50);
  color: var(--navy);
  font-size: 0.8125rem;
  font-weight: 600;
}

.profil__menu {
  display: flex;
  flex-direction: column;
  padding-block: 8px;
  border-block: 1px solid var(--garis-lembut);
}

.profil__menu a {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 44px;
  color: var(--teks);
  font-weight: 600;
  text-decoration: none;
}

.profil__menu a:hover {
  color: var(--navy);
}
</style>
