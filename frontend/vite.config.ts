import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Reachable from ngrok / LAN; Host-header allowlist covers rotating free-tier subdomains.
    host: true,
    allowedHosts: ['.ngrok-free.dev', '.ngrok-free.app'],
  },
  build: {
    lib: {
      entry: 'src/index.ts',
      name: 'SkeldirUI',
      fileName: 'skeldir-ui',
    },
    rollupOptions: {
      external: ['react', 'react-dom', 'react-router', 'react-router-dom'],
    },
  },
})
