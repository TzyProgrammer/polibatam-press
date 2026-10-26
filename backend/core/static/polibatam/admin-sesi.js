// Batas waktu tidak aktif Django Admin (pasangan core.sesi.BatasSesiAdminMiddleware).
// - Selama admin aktif (mengetik, mengklik, menggulir), server diberi tahu paling sering tiap 5 menit,
//   agar sesi tidak berakhir saat admin sedang mengisi formulir panjang tanpa berpindah halaman.
// - Bila tidak ada aktivitas selama batas waktu, halaman dimuat ulang; server lalu mengakhiri sesi dan
//   mengarahkan ke halaman masuk, sehingga data tidak tetap terlihat di layar yang ditinggalkan.
(() => {
  const skrip = document.currentScript
  const menit = Number(skrip?.dataset.menit) || 30
  const urlPing = skrip?.dataset.ping
  const BATAS_MS = menit * 60 * 1000
  const JEDA_PING_MS = Math.min(5 * 60 * 1000, BATAS_MS / 2)
  let aktifTerakhir = Date.now()
  let pingTerakhir = Date.now()

  function tandaiAktif() {
    aktifTerakhir = Date.now()
    if (urlPing && aktifTerakhir - pingTerakhir >= JEDA_PING_MS) {
      pingTerakhir = aktifTerakhir
      fetch(urlPing, { credentials: 'same-origin', cache: 'no-store' }).catch(() => {})
    }
  }

  for (const jenis of ['pointerdown', 'keydown', 'wheel', 'touchstart', 'input']) {
    document.addEventListener(jenis, tandaiAktif, { passive: true, capture: true })
  }

  setInterval(() => {
    if (Date.now() - aktifTerakhir >= BATAS_MS) window.location.reload()
  }, 30 * 1000)
})()
