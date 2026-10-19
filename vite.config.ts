import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  // The API listens on 127.0.0.1 only. The browser talks to Vite, and Vite
  // forwards /api there, so the app and the API share one origin (no CORS).
  const apiTarget = env.LEXFLOW_API_PROXY_TARGET || 'http://127.0.0.1:8000';
  const proxy = { '/api': { target: apiTarget } };

  return {
    plugins: [react()],
    server: {
      port: 5173,
      open: true,
      proxy,
    },
    preview: {
      proxy,
    },
  };
});
