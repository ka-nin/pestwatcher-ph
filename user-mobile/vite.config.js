import react from '@vitejs/plugin-react'
import basicSsl from '@vitejs/plugin-basic-ssl'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), basicSsl()],
  server: {
    port: 5173,
    open: true,
    // Exposes the dev server on the LAN (not just localhost) so a phone on
    // the same Wi-Fi can reach it. HTTPS (via basicSsl above) is required
    // because mobile browsers block getUserMedia (camera access) on any
    // non-localhost origin served over plain HTTP.
    host: true,
  },
})
