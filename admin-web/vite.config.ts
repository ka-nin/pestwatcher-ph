import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Pinned explicitly (matches Vite's default) so this never drifts onto
    // user-mobile's port — that app is pinned to 5174 for the same reason.
    port: 5173,
  },
})
