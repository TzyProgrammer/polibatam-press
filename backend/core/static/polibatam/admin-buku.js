// Halaman tambah/ubah Buku di Django Admin: perilaku baris produk (inline "produk").
// - Buku cetak: kolom berkas dikunci; ebook/audiobook: kolom stok dikunci (bernilai 0).
// - Format yang sudah dipakai baris lain tidak bisa dipilih lagi (satu baris per format; tombol Tambah
//   hilang sendiri setelah tiga baris karena max_num inline).
// - Label Jumlah halaman dan Ukuran ditandai wajib bila ada produk cetak atau ebook (sama dengan
//   BukuAdminForm.clean di server).
// - Tombol Hapus berkas dan Hapus produk membuka modal konfirmasi (admin-modal.js), lalu langsung diproses
//   server tanpa perlu menekan Simpan Perubahan; halaman dimuat ulang agar formulir kembali sinkron.
;(() => {
  const PREFIX = 'produk'
  const CATATAN_HILANG = ' Halaman akan dimuat ulang; perubahan lain yang belum disimpan di halaman ini akan hilang.'

  function grup() {
    return document.getElementById(`${PREFIX}-group`)
  }

  function barisProduk() {
    const wadah = grup()
    if (!wadah) return []
    return [...wadah.querySelectorAll('tr.form-row')].filter((baris) => !baris.classList.contains('empty-form'))
  }

  function aturCatatan(td, teks) {
    if (!td) return
    let catatan = td.querySelector('.catatan-format')
    if (!teks) {
      catatan?.remove()
      return
    }
    if (!catatan) {
      catatan = document.createElement('span')
      catatan.className = 'catatan-format'
      td.append(catatan)
    }
    catatan.textContent = teks
  }

  function aturBaris(baris) {
    const pilih = baris?.querySelector(`select[name$="-format"]`)
    if (!pilih) return
    const format = pilih.value
    const cetak = format === 'cetak'
    const digital = format === 'ebook' || format === 'audiobook'

    const stok = baris.querySelector(`input[name$="-stok"]`)
    if (stok) {
      stok.readOnly = !cetak
      if (!cetak) stok.value = '0'
      stok.closest('td')?.classList.toggle('kolom-tidak-berlaku', !cetak)
      aturCatatan(stok.closest('td'), cetak ? '' : digital ? 'Hanya untuk buku cetak' : '')
    }

    const berkas = baris.querySelector(`input[type="file"][name$="-berkas"]`)
    if (berkas) {
      berkas.disabled = !digital
      if (!digital) berkas.value = ''
      berkas.accept = format === 'ebook' ? '.pdf,application/pdf' : format === 'audiobook' ? '.mp3,audio/mpeg' : ''
      berkas.closest('td')?.classList.toggle('kolom-tidak-berlaku', !digital)
      aturCatatan(
        berkas.closest('td'),
        cetak ? 'Buku cetak tidak memakai berkas' : !format ? 'Pilih format dahulu' : format === 'ebook' ? 'Berkas PDF' : 'Berkas MP3',
      )
    }
  }

  function aturPilihanFormat() {
    const semua = barisProduk()
      .map((baris) => baris.querySelector(`select[name$="-format"]`))
      .filter(Boolean)
    const terpakai = semua.map((pilih) => pilih.value).filter(Boolean)
    for (const pilih of semua) {
      for (const opsi of pilih.options) {
        if (opsi.value) opsi.disabled = opsi.value !== pilih.value && terpakai.includes(opsi.value)
      }
    }
  }

  function aturWajibBacaan() {
    const format = barisProduk()
      .map((baris) => baris.querySelector('select[name$="-format"]')?.value)
      .filter(Boolean)
    const wajib = format.includes('cetak') || format.includes('ebook')
    for (const id of ['id_jumlah_halaman', 'id_ukuran']) {
      document.querySelector(`label[for="${id}"]`)?.classList.toggle('required', wajib)
    }
  }

  function aturSemua() {
    barisProduk().forEach(aturBaris)
    aturPilihanFormat()
    aturWajibBacaan()
  }

  document.addEventListener('change', (event) => {
    if (event.target.matches?.(`#${PREFIX}-group select[name$="-format"]`)) {
      aturBaris(event.target.closest('tr'))
      aturPilihanFormat()
      aturWajibBacaan()
    }
  })
  document.addEventListener('formset:added', (event) => {
    if (event.detail?.formsetName && event.detail.formsetName !== PREFIX) return
    aturBaris(event.target)
    aturPilihanFormat()
    aturWajibBacaan()
  })
  document.addEventListener('formset:removed', () => {
    aturPilihanFormat()
    aturWajibBacaan()
  })

  document.addEventListener('click', async (event) => {
    const tombolBerkas = event.target.closest?.('[data-hapus-berkas]')
    const tombolProduk = event.target.closest?.('[data-hapus-produk]')
    if (!tombolBerkas && !tombolProduk) return
    event.preventDefault()
    const { konfirmasi, kirim } = window.PolibatamAdmin
    const berhasil = tombolBerkas
      ? await konfirmasi({
          judul: 'Hapus berkas ini?',
          pesan: (tombolBerkas.dataset.pesan || 'Berkas dihapus permanen dari penyimpanan.') + CATATAN_HILANG,
          teksYa: 'Hapus berkas',
          aksi: () => kirim(tombolBerkas.dataset.hapusBerkas),
        })
      : await konfirmasi({
          judul: `Hapus produk ${tombolProduk.dataset.format || ''}?`.replace(' ?', '?'),
          pesan:
            'Produk ini dan berkasnya dihapus permanen dari buku. Tindakan ini tidak bisa dibatalkan.' + CATATAN_HILANG,
          teksYa: 'Hapus produk',
          aksi: () => kirim(tombolProduk.dataset.hapusProduk),
        })
    if (berhasil) window.location.reload()
  })

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', aturSemua)
  else aturSemua()
})()
