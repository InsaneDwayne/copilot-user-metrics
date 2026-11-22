import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // The dev server proxies the API so the session cookie and the OAuth callback
  // (http://localhost:5173/auth/github/callback) live on the browser's origin.
  const apiTarget = env.API_PROXY_TARGET ?? 'http://127.0.0.1:8000'
  return {
    plugins: [react(), tailwindcss()],
    // `@/…` is `src/…` (also in tsconfig.app.json).
    resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        '/api': { target: apiTarget, xfwd: true },
        '/auth': { target: apiTarget, xfwd: true },
      },
    },
    build: {
      // React, the router and zod are most of it; ~180 kB gzipped is expected.
      chunkSizeWarningLimit: 700,
    },
    test: {
      environment: 'node',
      // Let tokens.test.ts read the stylesheet's source (?raw) instead of an empty stub.
      css: { include: [/index\.css/] },
    },
  }
})
