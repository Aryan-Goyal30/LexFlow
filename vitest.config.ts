import { defineConfig, mergeConfig } from 'vitest/config';
import viteConfig from './vite.config';

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      css: false,
      // Reset vi.fn() call history and implementations, and undo vi.spyOn(),
      // before every test so tests can't leak into each other.
      mockReset: true,
      restoreMocks: true,
    },
  }),
);
