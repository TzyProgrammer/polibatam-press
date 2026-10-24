import { createApp } from 'vue'
import { createPinia } from 'pinia'

// Font disimpan sendiri (lisensi OFL), tidak memuat dari Google Fonts. Hanya subset Latin dan Latin
// Extended (huruf beraksen) yang dibutuhkan teks berbahasa Indonesia.
import '@fontsource/montserrat/latin-600.css'
import '@fontsource/montserrat/latin-ext-600.css'
import '@fontsource/montserrat/latin-700.css'
import '@fontsource/montserrat/latin-ext-700.css'
import '@fontsource/open-sans/latin-400.css'
import '@fontsource/open-sans/latin-ext-400.css'
import '@fontsource/open-sans/latin-600.css'
import '@fontsource/open-sans/latin-ext-600.css'
import '@fontsource/open-sans/latin-700.css'
import '@fontsource/open-sans/latin-ext-700.css'
import './styles/tokens.css'
import './styles/dasar.css'

import App from './App.vue'
import { aturSesi } from './api/klien'
import router from './router'
import { useAuthStore } from './stores/auth'
import { usePesanStore } from './stores/pesan'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)

const auth = useAuthStore(pinia)
const pesan = usePesanStore(pinia)

aturSesi({
  akses: () => auth.akses,
  segarkan: () => auth.segarkanAkses(),
  // Refresh token ditolak (kedaluwarsa, sudah dipakai, atau akun dinonaktifkan): keluar dan, bila
  // halaman ini butuh login, arahkan ke halaman Masuk.
  habis: () => {
    const tadinyaMasuk = auth.sudahMasuk
    auth.bersihkan()
    if (tadinyaMasuk) pesan.tampilkan('Sesi Anda sudah berakhir. Silakan masuk kembali.', { jenis: 'galat' })
    const sekarang = router.currentRoute.value
    if (sekarang.meta.perluMasuk) router.replace({ name: 'masuk', query: { next: sekarang.fullPath } })
  },
})

app.use(router)
app.mount('#app')
