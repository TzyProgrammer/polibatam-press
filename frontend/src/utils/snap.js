// Snap.js Midtrans dimuat hanya saat pembeli akan membayar (bukan di setiap halaman), sekali per tab.
// Alamat skrip dan client key berasal dari API detail pesanan (`pembayaran.snap_js`, `pembayaran.client_key`);
// server key tidak pernah sampai ke peramban.
let janjiSnap = null

export function muatSnap(src, clientKey) {
  if (window.snap) return Promise.resolve(window.snap)
  if (!src || !clientKey) return Promise.reject(new Error('Konfigurasi Snap belum lengkap.'))
  if (!janjiSnap) {
    janjiSnap = new Promise((berhasil, gagal) => {
      const skrip = document.createElement('script')
      skrip.src = src
      skrip.async = true
      skrip.dataset.clientKey = clientKey // dibaca snap.js dari atribut data-client-key
      skrip.onload = () => {
        if (window.snap) {
          berhasil(window.snap)
          return
        }
        janjiSnap = null
        gagal(new Error('snap.js dimuat, tetapi objek snap tidak tersedia.'))
      }
      skrip.onerror = () => {
        janjiSnap = null
        skrip.remove()
        gagal(new Error('snap.js gagal dimuat.'))
      }
      document.head.append(skrip)
    })
  }
  return janjiSnap
}

// Setelah checkout, halaman pembayaran langsung membuka jendela Snap satu kali. Disimpan di memori saja,
// jadi memuat ulang halaman pembayaran tidak membuka jendela itu lagi.
let nomorBukaOtomatis = null

export function tandaiBukaOtomatis(nomor) {
  nomorBukaOtomatis = nomor
}

export function ambilBukaOtomatis(nomor) {
  const cocok = nomorBukaOtomatis === nomor
  nomorBukaOtomatis = null
  return cocok
}
