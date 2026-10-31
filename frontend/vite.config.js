import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

// Beim Entwickeln (npm run dev) leitet Vite alle /api-Anfragen an das
// Python-Backend weiter. Im Alltag liefert das Backend das gebaute Frontend aus.
export default defineConfig({
  plugins: [svelte()],
  server: {
    host: '127.0.0.1',
    proxy: { '/api': 'http://127.0.0.1:8765' },
  },
})
