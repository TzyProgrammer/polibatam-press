import { ref } from 'vue'

// Tema tampilan: "sistem" (mengikuti pengaturan perangkat), "terang", atau "gelap", seperti tombol tema
// Django Admin. Pilihan disimpan di localStorage peramban ini saja. Atribut data-tema pada <html> dipasang
// paling awal oleh skrip kecil di index.html agar halaman tidak sempat berkedip terang; berkas ini
// mengubahnya saat pengguna memilih tema lain. Warna tiap tema ada di styles/tokens.css.
const KUNCI = 'polibatam-press.tema'
export const URUTAN_TEMA = ['sistem', 'terang', 'gelap']
export const LABEL_TEMA = { sistem: 'Sistem', terang: 'Terang', gelap: 'Gelap' }

function bacaTema() {
  try {
    const tersimpan = localStorage.getItem(KUNCI)
    return URUTAN_TEMA.includes(tersimpan) ? tersimpan : 'sistem'
  } catch {
    return 'sistem'
  }
}

export const tema = ref(bacaTema())

export function pilihTema(pilihan) {
  const nilai = URUTAN_TEMA.includes(pilihan) ? pilihan : 'sistem'
  tema.value = nilai
  const akar = document.documentElement
  if (nilai === 'sistem') delete akar.dataset.tema
  else akar.dataset.tema = nilai
  try {
    if (nilai === 'sistem') localStorage.removeItem(KUNCI)
    else localStorage.setItem(KUNCI, nilai)
  } catch {
    // localStorage tidak tersedia (mode privat ketat): tema tetap berlaku sampai halaman ditutup.
  }
}

// Urutan tombol sama dengan Django Admin: sistem → terang → gelap → sistem.
export function temaBerikutnya(sekarang = tema.value) {
  return URUTAN_TEMA[(URUTAN_TEMA.indexOf(sekarang) + 1) % URUTAN_TEMA.length]
}
