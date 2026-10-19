import { stopBackend } from './support/backend';

export default async function globalTeardown() {
  await stopBackend();
}
