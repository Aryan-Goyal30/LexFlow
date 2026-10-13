import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// jsdom has no object URLs. These stand in for the browser at that boundary;
// tests spy on them to check that URLs are created and revoked.
let objectUrlCount = 0;
Object.defineProperty(URL, 'createObjectURL', {
  configurable: true,
  writable: true,
  value: () => `blob:lexflow-test/${++objectUrlCount}`,
});
Object.defineProperty(URL, 'revokeObjectURL', {
  configurable: true,
  writable: true,
  value: () => undefined,
});

afterEach(() => {
  cleanup();
  localStorage.clear();
});
