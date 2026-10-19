import '@testing-library/jest-dom/vitest';
import { Blob as NodeBlob, File as NodeFile } from 'node:buffer';
import { cleanup } from '@testing-library/react';
import { afterAll, afterEach, beforeAll, beforeEach } from 'vitest';
import { resetMockApi, server } from './mockApi';

// In the jsdom environment `fetch` is Node's, while File/Blob/FormData are
// jsdom's. Node's fetch can't serialise jsdom's FormData (it would send the
// text "[object FormData]"), so uploads use Node's classes, as a real browser
// uses its own matching set. Node exposes FormData only through a Response.
const NodeFormData = (
  await new Response('probe=1', {
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
  }).formData()
).constructor as typeof FormData;
Object.assign(globalThis, { File: NodeFile, Blob: NodeBlob, FormData: NodeFormData });

// The API is replaced by MSW at the network boundary. Any request without a
// handler fails the test instead of silently reaching the network.
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
beforeEach(() => resetMockApi());
afterEach(() => {
  cleanup();
  server.resetHandlers();
  localStorage.clear();
});
afterAll(() => server.close());
