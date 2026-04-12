import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  // Set base to the GitHub repo name for GitHub Pages
  // Update this if your repo name changes
  base: '/OTTER/',
})
