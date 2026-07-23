import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

function manualChunks(id: string): string | undefined {
  if (!id.includes('node_modules')) return undefined
  if (id.includes('/naive-ui/') || id.includes('/vueuc/') || id.includes('/vdirs/') || id.includes('/vooks/') || id.includes('/treemate/') || id.includes('/seemly/') || id.includes('/css-render/')) return 'ui-vendor'
  if (id.includes('/vue/') || id.includes('/vue-router/') || id.includes('/pinia/')) return 'vue-vendor'
  if (id.includes('/katex/')) return 'katex'
  if (id.includes('/@vicons/')) return 'icons'
  return 'vendor'
}

export default defineConfig(({ command }) => ({
  // The FastAPI host exposes production files under /ui/. Keep the dev server at
  // the root so `npm run dev` continues to open directly on port 5173.
  base: command === 'build' ? '/ui/' : '/',
  plugins: [vue()],
  build: {
    rollupOptions: {
      output: { manualChunks }
    }
  },
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
