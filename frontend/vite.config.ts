import fs from 'node:fs'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

function backendTarget() {
  if (process.env.VITE_PROXY_TARGET) return process.env.VITE_PROXY_TARGET
  try {
    if (fs.existsSync('/proc/version')) {
      const proc = fs.readFileSync('/proc/version', 'utf8')
      if (/microsoft/i.test(proc) && fs.existsSync('/etc/resolv.conf')) {
        const text = fs.readFileSync('/etc/resolv.conf', 'utf8')
        const match = text.match(/nameserver\s+(\S+)/)
        if (match?.[1]) return `http://${match[1]}:8000`
      }
    }
  } catch {
    // Use loopback when the host is the same OS as Vite.
  }
  return 'http://127.0.0.1:8000'
}

const target = backendTarget()

export default defineConfig({
  plugins: [react()],
  server: {
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
