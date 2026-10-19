import { clearStaleRecord, prepareDatabase, startBackend } from './support/backend';

export default async function globalSetup() {
  await clearStaleRecord();
  prepareDatabase();
  await startBackend();
}
