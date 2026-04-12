import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'   // ← back to this

export default defineConfig({
  plugins: [react()],
  base: '/OTTER/',
})