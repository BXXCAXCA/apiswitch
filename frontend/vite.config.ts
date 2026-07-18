import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ command }) => ({
  // The FastAPI host exposes production files under /ui/. Keep the dev server at
  // the root so `npm run dev` continues to open directly on port 5173.
  base: command === 'build' ? '/ui/' : '/',
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts']
  },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8080',
      '/v1': 'http://127.0.0.1:8080',
      '/health': 'http://127.0.0.1:8080'
    }
  }
}))
