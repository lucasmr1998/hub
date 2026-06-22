import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev: Vite dev server (5173) com proxy pro Django (8001).
// Build: sai na pasta de estáticos do Django, com nomes previsíveis (sem hash),
// pra o template servir editor.js/editor.css direto. Assim em "produção" é UM app
// só (Django serve o bundle em /automacao/editor/), sem segundo porto.
export default defineConfig(({ command }) => ({
  plugins: [react()],
  base: command === 'build' ? '/static/automacao_editor/' : '/',
  server: {
    port: 5173,
    proxy: {
      '/automacao/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: '../static/automacao_editor',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: 'editor.js',
        chunkFileNames: 'editor-[name].js',
        assetFileNames: 'editor.[ext]',
      },
    },
  },
}))
