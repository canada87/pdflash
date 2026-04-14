import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  server: {
    port: 5173,
    host: true,   // ascolta su 0.0.0.0, raggiungibile via IP della macchina
    proxy: {
      '/api':   { target: 'http://localhost:8000', changeOrigin: true },
      '/cache': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  build: {
    outDir: '../backend/static',
    emptyOutDir: true,
  },
});
