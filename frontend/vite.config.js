import { createReadStream, existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { createRequire } from 'node:module'
import { basename, dirname, extname, join, resolve, sep } from 'node:path'

import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

// Berkas bantu PDF.js (font standar, wasm dekoder gambar, CMap, profil ICC) disajikan di /pdfjs/<folder>/
// langsung dari node_modules/pdfjs-dist: lewat middleware saat `npm run dev`, dan disalin ke dist/pdfjs/
// saat `npm run build`. Dengan begitu berkas biner ini tidak perlu ikut di-commit dan selalu sama versinya
// dengan pdfjs-dist yang terpasang.
const require = createRequire(import.meta.url)
const FOLDER_PDFJS = dirname(require.resolve('pdfjs-dist/package.json'))
const ASET_PDFJS = ['cmaps', 'iccs', 'standard_fonts', 'wasm']

// Font Liberation Sans 1.x bawaan pdfjs-dist berlisensi GPLv2 (dengan pengecualian font), jadi tidak ikut
// disajikan. PDF.js hanya memakainya sebagai cadangan terakhir untuk teks Helvetica yang fontnya tidak
// di-embed, setelah font sistem (Helvetica, Arial, DejaVu Sans, dan lain-lain); tanpa berkas ini peramban
// memakai font sans-serif bawaan. Font standar lain (Foxit) berlisensi BSD.
function dikecualikan(folder, nama) {
  return folder === 'standard_fonts' && /^(LiberationSans-|LICENSE_LIBERATION)/.test(nama)
}
const JENIS_BERKAS = {
  '.wasm': 'application/wasm',
  '.js': 'text/javascript',
  '.ttf': 'font/ttf',
  '.pfb': 'application/octet-stream',
  '.bcmap': 'application/octet-stream',
  '.icc': 'application/octet-stream',
}

function asetPdfjs() {
  return {
    name: 'aset-pdfjs',
    configureServer(server) {
      server.middlewares.use('/pdfjs', (req, res, next) => {
        let jalur
        try {
          jalur = decodeURIComponent((req.url || '').split('?')[0]).replace(/^\/+/, '')
        } catch {
          next()
          return
        }
        const berkas = resolve(FOLDER_PDFJS, jalur)
        const folder = ASET_PDFJS.find((nama) => berkas.startsWith(join(FOLDER_PDFJS, nama) + sep))
        if (!folder || dikecualikan(folder, basename(berkas)) || !existsSync(berkas) || !statSync(berkas).isFile()) {
          next()
          return
        }
        res.setHeader('Content-Type', JENIS_BERKAS[extname(berkas)] || 'application/octet-stream')
        createReadStream(berkas).pipe(res)
      })
    },
    generateBundle() {
      for (const folder of ASET_PDFJS) {
        for (const nama of readdirSync(join(FOLDER_PDFJS, folder))) {
          const berkas = join(FOLDER_PDFJS, folder, nama)
          if (dikecualikan(folder, nama) || !statSync(berkas).isFile()) continue
          this.emitFile({ type: 'asset', fileName: `pdfjs/${folder}/${nama}`, source: readFileSync(berkas) })
        }
      }
    },
  }
}

// Permintaan ke /api diteruskan ke backend (Nginx di Docker, bawaan http://127.0.0.1:8080), sehingga
// peramban hanya melihat satu origin (localhost:5173) dan API tidak memerlukan CORS.
// changeOrigin: false menjaga header Host tetap localhost:5173. Nginx meneruskannya ($http_host),
// sehingga URL absolut buatan Django (misalnya playlist audiobook) juga lewat proxy ini.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const proxy = {
    '/api': { target: env.VITE_BACKEND || 'http://127.0.0.1:8080', changeOrigin: false },
  }
  return {
    plugins: [vue(), asetPdfjs()],
    // Pustaka yang dimuat belakangan (pembaca ebook, pemutar audiobook) disiapkan saat server dev mulai,
    // agar halaman tidak dimuat ulang Vite saat pertama kali dibuka.
    optimizeDeps: { include: ['pdfjs-dist/legacy/build/pdf.mjs', 'hls.js/light'] },
    server: { port: 5173, strictPort: true, proxy },
    preview: { port: 4173, strictPort: true, proxy },
  }
})
