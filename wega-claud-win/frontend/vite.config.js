import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const backendHttp = 'http://localhost:6060';
const backendWs = 'ws://localhost:6060';
const backendUnavailable = {
  error: 'Quantnik backend is unavailable. Start or restart the backend on port 6060, then refresh the page.',
};

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      '/api': {
        target: backendHttp,
        changeOrigin: true,
        configure(proxy) {
          proxy.on('error', (_err, _req, res) => {
            if (!res || res.destroyed) return;
            if (!res.headersSent) {
              res.writeHead(503, { 'Content-Type': 'application/json' });
            }
            res.end(JSON.stringify(backendUnavailable));
          });
        },
      },
      '/ws': { target: backendWs, ws: true },
    },
  },
});
