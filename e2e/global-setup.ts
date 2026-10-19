import { clearStaleRecord, prepareDatabase, startBackend } from './support/backend';
import { SIGNED_IN, newRunPassword, saveCredentials, saveSignedInState } from './support/accounts';

export default async function globalSetup() {
  await clearStaleRecord();
  const password = newRunPassword();
  prepareDatabase(password);
  saveCredentials(password);
  await startBackend();
  for (const account of SIGNED_IN) await saveSignedInState(account, password);
}
