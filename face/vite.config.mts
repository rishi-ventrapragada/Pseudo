// M18: Vite only BUILDS the page into dist/ (npm run build), and Vitest runs the page's tests.
// Vite's dev server is never used: it would listen on a port, and the face has none (D18).
// M39: Tailwind runs inside the build (no CDN, nothing at run time). assetsInlineLimit 0 keeps every file a
// real file in dist/: Vite would otherwise turn small files (icons, fonts) into data: URIs, which the page's
// security policy (index.html, default-src 'self') refuses.
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: { outDir: 'dist', emptyOutDir: true, assetsInlineLimit: 0 },
});
