// M18: Vite only BUILDS the page into dist/ (npm run build), and Vitest runs the page's tests.
// Vite's dev server is never used: it would listen on a port, and the face has none (D18).
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  build: { outDir: 'dist', emptyOutDir: true },
});
