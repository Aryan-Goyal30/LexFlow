import { stopBackend, stopWorker } from './support/backend';

export default async function globalTeardown() {
  await stopWorker();
  await stopBackend();
}
