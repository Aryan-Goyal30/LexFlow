/**
 * Sign-in accounts for the end-to-end tests.
 *
 * Each run gets a new random password (`newRunPassword`). Global setup passes it
 * to `server/scripts/e2e.py prepare` in an environment variable (never on a
 * command line, which other processes can read) and keeps it only in
 * `e2e/.state/credentials.json` (git-ignored, not uploaded by CI). The accounts
 * exist only in the throwaway `lexflow_e2e` database; `E2E_ACCOUNTS` in
 * `e2e.py` lists the same addresses.
 *
 * Global setup also signs the main roles in through the API and saves each
 * session as a Playwright storage state, so most tests start signed in without
 * typing a password.
 */

import { randomBytes } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { API_PORT, APP_PORT } from './backend';

export const ACCOUNTS = {
  admin: 'e2e.admin@lexflow.test',
  advocate: 'aryan.goyal@lexflow.test', // the sample lead advocate
  lockout: 'e2e.lockout@lexflow.test', // only for the lockout test
  paralegal: 'e2e.paralegal@lexflow.test', // on the Sattvik case team
  outsider: 'rajat.deshpande@lexflow.test', // an Advocate who leads a different case
  client: 'e2e.client@client.example', // a Client account for the Sattvik case's client
} as const;

export type Account = keyof typeof ACCOUNTS;

/** Accounts that get a saved, signed-in browser state. */
export const SIGNED_IN: Account[] = ['admin', 'advocate', 'paralegal', 'outsider', 'client'];

const STATE_DIR = fileURLToPath(new URL('../.state', import.meta.url));
const CREDENTIALS = path.join(STATE_DIR, 'credentials.json');
export const APP_ORIGIN = `http://localhost:${APP_PORT}`;

export const storageStatePath = (account: Account) => path.join(STATE_DIR, `${account}.json`);

export function newRunPassword(): string {
  return randomBytes(24).toString('base64url'); // 32 characters
}

export function saveCredentials(password: string): void {
  mkdirSync(STATE_DIR, { recursive: true });
  writeFileSync(CREDENTIALS, JSON.stringify({ password }), { mode: 0o600 });
}

export function runPassword(): string {
  return (JSON.parse(readFileSync(CREDENTIALS, 'utf8')) as { password: string }).password;
}

/** Sign in through the API and save the session cookie for the app's origin. */
export async function saveSignedInState(account: Account, password: string): Promise<void> {
  const response = await fetch(`http://127.0.0.1:${API_PORT}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Origin: APP_ORIGIN, 'X-LexFlow-Request': '1' },
    body: JSON.stringify({ email: ACCOUNTS[account], password }),
  });
  if (!response.ok) {
    throw new Error(`Signing in the e2e ${account} account failed (${response.status}).`);
  }
  const value = response.headers
    .getSetCookie()
    .find((cookie) => cookie.startsWith('lexflow_session='))
    ?.split(';')[0]
    .slice('lexflow_session='.length);
  if (!value) throw new Error('The sign-in response set no session cookie.');
  const state = {
    cookies: [
      {
        name: 'lexflow_session',
        value,
        domain: 'localhost',
        path: '/',
        expires: -1,
        httpOnly: true,
        secure: false,
        sameSite: 'Strict',
      },
    ],
    origins: [],
  };
  writeFileSync(storageStatePath(account), JSON.stringify(state), { mode: 0o600 });
}
