import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

function backendTarget() {
  if (process.env.VITE_PROXY_TARGET) return process.env.VITE_PROXY_TARGET
  return 'http://127.0.0.1:8000'
}

const target = backendTarget()

export default defineConfig({
  plugins: [react()],
  server: {
    watch: {
      usePolling: true,
      interval: 1000,
    },
    proxy: {
      '/api': { target, changeOrigin: true },
      '/health': { target, changeOrigin: true },
    },
  },
  preview: {
    proxy: {
      '/api': { target, changeOrigin: true },
      '/health': { target, changeOrigin: true },
    },
  },
})
