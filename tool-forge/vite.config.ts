import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  // Relative base so the app works from any hosting path (GitHub Pages subpath, Render root)
  base: './',
  plugins: [react(), tailwindcss()],
})
