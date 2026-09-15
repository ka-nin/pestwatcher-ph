import react from '@vitejs/plugin-react'
import basicSsl from '@vitejs/plugin-basic-ssl'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [
    react(),
    // HTTPS is only actually needed for the real-phone/LAN camera test (see
    // README section 6) — mobile browsers block getUserMedia (camera access)
    // on any non-localhost origin served over plain HTTP. Plain http on
    // "localhost" itself is already a secure context per spec, so it doesn't
    // need this. Embedded webviews (VS Code's Simple Browser, the
    // "Responsive Viewer" extension, etc.) generally can't offer the
    // click-through prompt a real browser tab does for a self-signed cert —
    // they just silently fail to load instead. Run `npm run dev:preview` to
    // skip this plugin and get a plain-HTTP server for previewing in those
    // tools; use the normal `npm run dev` for real-phone camera testing.
    ...(mode === 'http-preview' ? [] : [basicSsl()]),
  ],
  server: {
    port: 5173,
    open: true,
    host: true,
  },
}))
