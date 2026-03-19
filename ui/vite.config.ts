import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { visualizer } from 'rollup-plugin-visualizer';
import path from 'path';

export default defineConfig({
  plugins: [
    react(),
    ...(process.env.ANALYZE ? [visualizer({ open: true, gzipSize: true })] : []),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        // Phase 75.4 baseline (2026-03-08, Vite 7 + MUI v7):
        //   vendor-mui: 129KB gz, vendor-datagrid: 119KB gz, vendor-charts: 81KB gz,
        //   index (app shell): 97KB gz, vendor-react: 17KB gz, vendor-query: 11KB gz.
        //   All @mui/icons-material imports use deep paths (tree-shakeable).
        //   date-fns imports are per-function. No barrel-import issues found.
        // Vite 8 / Rolldown requires manualChunks as a function, not an object.
        manualChunks(id: string) {
          if (id.includes('node_modules/react-dom/') || id.includes('node_modules/react/') || id.includes('node_modules/react-router-dom/')) {
            return 'vendor-react';
          }
          if (id.includes('node_modules/@mui/material/') || id.includes('node_modules/@mui/icons-material/') || id.includes('node_modules/@emotion/')) {
            return 'vendor-mui';
          }
          if (id.includes('node_modules/@tanstack/react-query/')) {
            return 'vendor-query';
          }
          if (id.includes('node_modules/@mui/x-charts/')) {
            return 'vendor-charts';
          }
          if (id.includes('node_modules/@mui/x-data-grid/')) {
            return 'vendor-datagrid';
          }
        },
      },
    },
  },
  server: {
    port: 5173,
    host: '127.0.0.1',
    proxy: {
      '/api': {
        target: 'http://localhost:5056',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:5056',
        changeOrigin: true,
      },
    },
  },
});
