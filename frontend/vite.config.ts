import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

// https://vite.dev/config/
export default defineConfig({
  base: '/app-v2/',
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/auth': 'http://127.0.0.1:8002',
      '/agent': 'http://127.0.0.1:8002',
      '/conversations': 'http://127.0.0.1:8002',
      '/sources': 'http://127.0.0.1:8002',
      '/documents': 'http://127.0.0.1:8002',
      '/feedback': 'http://127.0.0.1:8002',
      '/assets': 'http://127.0.0.1:8002',
      '/health': 'http://127.0.0.1:8002',
    },
  },
})
