import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// Standalone (not merged with vite.config.ts): tests need the React plugin but
// not the dev-server proxy, and the API is replaced by MSW at the network edge.
export default defineConfig({
  plugins: [react()],
  test: {
    // Unit and component tests only; e2e/ holds the Playwright tests.
    include: ['src/**/*.test.{ts,tsx}'],
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    // Reset vi.fn() call history and implementations, and undo vi.spyOn(),
    // before every test so tests can't leak into each other.
    mockReset: true,
    restoreMocks: true,
  },
});
