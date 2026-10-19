import { expect, test, type Page } from '@playwright/test';
import { ACCOUNTS, APP_ORIGIN, runPassword } from './support/accounts';

// Real sign-in through the browser, against the real API and database.

async function fillSignIn(page: Page, email: string, password: string) {
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
}

test('signs in with the form, signs out, and the old session is then useless', async ({
  page,
  context,
}) => {
  await page.goto('/app/cases');
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible(); // not signed in

  await fillSignIn(page, ACCOUNTS.admin, runPassword());
  await expect(page).toHaveURL(/\/app\/cases$/);
  await expect(page.getByText('E2E Administrator')).toBeVisible();

  const cookie = (await context.cookies()).find((c) => c.name === 'lexflow_session');
  expect(cookie).toBeDefined();
  expect(cookie?.httpOnly).toBe(true);
  expect(cookie?.sameSite).toBe('Strict');
  // HttpOnly: scripts on the page cannot read the session.
  expect(await page.evaluate(() => document.cookie)).not.toContain('lexflow_session');

  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible();
  await page.goto('/app/dashboard');
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible();

  // Replaying the old session cookie gets nothing: the server ended it.
  const replay = await page.request.get('/api/cases', {
    headers: { Cookie: `lexflow_session=${cookie?.value}` },
  });
  expect(replay.status()).toBe(401);
});

test('a wrong password gets the same answer as an unknown account', async ({ page }) => {
  await page.goto('/');
  await fillSignIn(page, ACCOUNTS.admin, 'not the right password');
  await expect(page.getByRole('alert')).toHaveText('Email or password is incorrect.');
  await fillSignIn(page, 'nobody@lexflow.test', runPassword());
  await expect(page.getByRole('alert')).toHaveText('Email or password is incorrect.');
  await expect(page).toHaveURL(/\/$/);
});

test('five wrong passwords lock the account: the sixth try fails even when right', async ({
  page,
}) => {
  await page.goto('/');
  for (let attempt = 1; attempt <= 5; attempt += 1) {
    await fillSignIn(page, ACCOUNTS.lockout, `wrong password ${attempt}`);
    await expect(page.getByRole('alert')).toHaveText('Email or password is incorrect.');
  }
  await fillSignIn(page, ACCOUNTS.lockout, runPassword());
  await expect(page.getByRole('alert')).toHaveText('Email or password is incorrect.');
  await expect(page).toHaveURL(/\/$/);
});

test('changes need the app header, and the dev server grants no CORS', async ({ request }) => {
  const preflight = await request.fetch('/api/cases', {
    method: 'OPTIONS',
    headers: {
      Origin: 'http://localhost:3000',
      'Access-Control-Request-Method': 'POST',
      'Access-Control-Request-Headers': 'x-lexflow-request',
    },
  });
  expect(preflight.headers()['access-control-allow-origin']).toBeUndefined();

  const withoutHeader = await request.post('/api/auth/login', {
    data: { email: ACCOUNTS.admin, password: runPassword() },
    headers: { Origin: APP_ORIGIN },
  });
  expect(withoutHeader.status()).toBe(403);
  expect((await withoutHeader.json()).code).toBe('csrf-header-missing');

  const otherOrigin = await request.post('/api/auth/login', {
    data: { email: ACCOUNTS.admin, password: runPassword() },
    headers: { Origin: 'http://localhost:3000', 'X-LexFlow-Request': '1' },
  });
  expect(otherOrigin.status()).toBe(403);
  expect((await otherOrigin.json()).code).toBe('forbidden-origin');
});
