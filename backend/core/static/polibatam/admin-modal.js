// Modal konfirmasi untuk tindakan yang tidak bisa dibatalkan di Django Admin Polibatam Press.
// PolibatamAdmin.konfirmasi({ judul, pesan, teksYa, aksi }) membuka <dialog>; tombol utama menjalankan
// aksi() (async). Bila aksi gagal (melempar Error), pesannya tampil di modal dan modal tetap terbuka.
// Fokus awal ada di tombol Batal agar Enter tidak langsung menghapus.
window.PolibatamAdmin = window.PolibatamAdmin || {}

window.PolibatamAdmin.konfirmasi = function konfirmasi({ judul, pesan, teksYa = 'Hapus', aksi }) {
  return new Promise((selesai) => {
    const dialog = document.createElement('dialog')
    dialog.className = 'modal-konfirmasi'
    dialog.setAttribute('aria-labelledby', 'modal-konfirmasi-judul')
    dialog.setAttribute('aria-describedby', 'modal-konfirmasi-pesan')

    const isi = document.createElement('div')
    isi.className = 'modal-konfirmasi__isi'
    const elJudul = document.createElement('h2')
    elJudul.id = 'modal-konfirmasi-judul'
    elJudul.className = 'modal-konfirmasi__judul'
    elJudul.textContent = judul
    const elPesan = document.createElement('p')
    elPesan.id = 'modal-konfirmasi-pesan'
    elPesan.className = 'modal-konfirmasi__pesan'
    elPesan.textContent = pesan
    const elGalat = document.createElement('p')
    elGalat.className = 'modal-konfirmasi__galat'
    elGalat.setAttribute('role', 'alert')
    elGalat.hidden = true
    isi.append(elJudul, elPesan, elGalat)

    const aksiBaris = document.createElement('div')
    aksiBaris.className = 'modal-konfirmasi__aksi'
    const batal = document.createElement('button')
    batal.type = 'button'
    batal.className = 'modal-konfirmasi__batal'
    batal.textContent = 'Batal'
    const ya = document.createElement('button')
    ya.type = 'button'
    ya.className = 'modal-konfirmasi__ya'
    ya.textContent = teksYa
    aksiBaris.append(batal, ya)

    dialog.append(isi, aksiBaris)
    document.body.append(dialog)

    let hasil = false
    function tutup() {
      dialog.close()
    }
    dialog.addEventListener('close', () => {
      dialog.remove()
      selesai(hasil)
    })
    batal.addEventListener('click', tutup)
    ya.addEventListener('click', async () => {
      ya.disabled = true
      batal.disabled = true
      ya.textContent = 'Memproses…'
      elGalat.hidden = true
      try {
        if (aksi) await aksi()
        hasil = true
        tutup()
      } catch (galat) {
        elGalat.textContent = galat?.message || 'Tindakan gagal. Coba lagi.'
        elGalat.hidden = false
        batal.disabled = false
        ya.disabled = false
        ya.textContent = teksYa
        batal.focus()
      }
    })

    dialog.showModal()
    batal.focus()
  })
}

// POST ke endpoint admin (CSRF dari formulir halaman); mengembalikan JSON atau melempar Error berisi pesan.
window.PolibatamAdmin.kirim = async function kirim(url) {
  const token = document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || ''
  let respons
  try {
    respons = await fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': token, 'X-Requested-With': 'XMLHttpRequest', Accept: 'application/json' },
    })
  } catch {
    throw new Error('Tidak dapat terhubung ke server. Periksa koneksi lalu coba lagi.')
  }
  let data = null
  try {
    data = await respons.json()
  } catch {
    data = null
  }
  if (!respons.ok) {
    if (respons.status === 403) throw new Error('Anda tidak memiliki izin untuk tindakan ini.')
    throw new Error(data?.pesan || `Tindakan gagal (HTTP ${respons.status}).`)
  }
  return data
}
