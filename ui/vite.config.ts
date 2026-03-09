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
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-mui': [
            '@mui/material',
            '@mui/icons-material',
            '@emotion/react',
            '@emotion/styled',
          ],
          'vendor-query': ['@tanstack/react-query'],
          'vendor-charts': ['@mui/x-charts'],
          'vendor-datagrid': ['@mui/x-data-grid'],
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
