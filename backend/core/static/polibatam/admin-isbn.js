// Halaman ubah Pengajuan ISBN di Django Admin: kolom yang tidak berlaku untuk status terpilih dikunci.
// - Nomor ISBN dan tanggal penetapan hanya untuk status Selesai; alasan penolakan hanya untuk Ditolak
//   (daftar status per kolom ada di atribut data-status-berlaku, dari KOLOM_PER_STATUS di isbn/admin.py).
// - Kolom terkunci tidak ikut dikirim (disabled) dan server juga mengosongkannya, jadi kunci ini bukan
//   satu-satunya pengaman. Isian yang sempat diketik tetap terlihat bila status dikembalikan.
;(() => {
  const LABEL_STATUS = { selesai: 'Selesai', ditolak: 'Ditolak' }

  function aturKolom() {
    const status = document.getElementById('id_status')
    if (!status) return
    for (const kolom of document.querySelectorAll('[data-status-berlaku]')) {
      const berlaku = kolom.dataset.statusBerlaku.split(' ')
      const aktif = berlaku.includes(status.value)
      kolom.disabled = !aktif
      const baris = kolom.closest('.form-row')
      if (!baris) continue
      baris.classList.toggle('kolom-terkunci', !aktif)
      // Pintasan "Hari ini" dan kalender di samping kolom tanggal (dibuat DateTimeShortcuts saat load).
      baris.querySelectorAll('.datetimeshortcuts').forEach((el) => {
        el.hidden = !aktif
      })
      let catatan = baris.querySelector('.catatan-terkunci')
      if (aktif) {
        catatan?.remove()
        continue
      }
      if (!catatan) {
        catatan = document.createElement('div')
        catatan.className = 'help catatan-terkunci'
        const wadah = kolom.closest('.flex-container')
        if (wadah) wadah.after(catatan)
        else kolom.after(catatan)
      }
      const daftar = berlaku.map((s) => LABEL_STATUS[s] || s).join(' atau ')
      catatan.textContent = `Terkunci: hanya diisi bila status ${daftar}.`
    }
  }

  document.addEventListener('change', (event) => {
    if (event.target.id === 'id_status') aturKolom()
  })
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', aturKolom)
  else aturKolom()
  window.addEventListener('load', aturKolom)
})()
