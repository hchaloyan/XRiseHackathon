import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

/**
 * `base` is set at build time, not hard-coded.
 *
 * The desktop app serves the UI from the root of its own origin, so it needs
 * '/'. GitHub Pages serves a project site from /<repo>/, and assets requested
 * from '/' there would 404 into a blank page. BASE_PATH is exported by the
 * Pages workflow and left unset everywhere else.
 *
 * https://vite.dev/config/
 */
export default defineConfig({
  base: process.env.BASE_PATH ?? '/',
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
  },
})
