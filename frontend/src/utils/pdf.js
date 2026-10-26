// PDF.js (pdfjs-dist, Apache-2.0) dimuat hanya saat pembaca ebook dibuka, agar halaman lain tetap ringan.
// Dipakai build "legacy": build modern PDF.js 6 memakai fitur JavaScript terbaru (misalnya
// Map.prototype.getOrInsertComputed) yang belum ada di peramban yang sedikit lebih lama, sedangkan build
// legacy menyertakan polyfill-nya. Berkas bantu (font standar, wasm, CMap, ICC) disajikan di /pdfjs/ oleh
// plugin di vite.config.js.
import urlWorker from 'pdfjs-dist/legacy/build/pdf.worker.min.mjs?url'

let janjiPdfjs = null

export function muatPdfjs() {
  if (!janjiPdfjs) {
    janjiPdfjs = import('pdfjs-dist/legacy/build/pdf.mjs')
      .then((pdfjs) => {
        pdfjs.GlobalWorkerOptions.workerSrc = urlWorker
        return pdfjs
      })
      .catch((galat) => {
        janjiPdfjs = null
        throw galat
      })
  }
  return janjiPdfjs
}

// Opsi getDocument untuk salinan ebook dari presigned URL (berlaku 5 menit): seluruh berkas diunduh sekali
// (tanpa permintaan rentang), sehingga halaman berikutnya tetap bisa dirender setelah URL kedaluwarsa.
export function opsiDokumen(url) {
  const basis = `${import.meta.env.BASE_URL}pdfjs/`
  return {
    url,
    disableRange: true,
    withCredentials: false,
    cMapUrl: `${basis}cmaps/`,
    iccUrl: `${basis}iccs/`,
    standardFontDataUrl: `${basis}standard_fonts/`,
    wasmUrl: `${basis}wasm/`,
  }
}
