import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

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
    plugins: [vue()],
    server: { port: 5173, strictPort: true, proxy },
    preview: { port: 4173, strictPort: true, proxy },
  }
})
