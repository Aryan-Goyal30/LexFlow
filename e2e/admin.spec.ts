import { expect, test } from '@playwright/test';
import { storageStatePath } from './support/accounts';

// Account administration against the real API: an Administrator creates an
// account, the person must replace the temporary password, and disabling the
// account ends their session.

test('a new account signs in, must change its password, and can be disabled', async ({
  browser,
}) => {
  const temporary = `temporary-${Date.now()}-passphrase`;
  const chosen = `chosen-${Date.now()}-passphrase`;
  const email = `e2e.new.${Date.now()}@lexflow.test`;

  const admin = await (
    await browser.newContext({ storageState: storageStatePath('admin') })
  ).newPage();
  await admin.goto('/app/admin/users');
  await admin.getByRole('button', { name: /New Account/ }).click();
  const form = admin.getByRole('form', { name: 'New account' });
  await form.getByLabel(/Name/).fill('E2E New Paralegal');
  await form.getByLabel(/E-mail/).fill(email);
  await form.getByLabel('Role').selectOption('Paralegal');
  await form.getByLabel(/Temporary password/).fill(temporary);
  await form.getByRole('button', { name: 'Create Account' }).click();
  await expect(admin.getByText(/^Created E2E New Paralegal\./)).toBeVisible();

  // The person signs in and is held at the password page until they change it.
  const person = await (await browser.newContext()).newPage();
  await person.goto('/');
  await person.getByLabel('Email address').fill(email);
  await person.getByLabel('Password', { exact: true }).fill(temporary);
  await person.getByRole('button', { name: 'Sign in' }).click();
  await expect(person).toHaveURL(/\/app\/account\/password$/);
  await person.getByLabel(/^Current password/).fill(temporary);
  await person.getByLabel(/^New password/).fill(chosen);
  await person.getByLabel(/^Repeat the new password/).fill(chosen);
  await person.getByRole('button', { name: 'Change password' }).click();
  await expect(person).toHaveURL(/\/app\/cases$/);
  expect((await person.request.get('/api/cases')).status()).toBe(200);

  // Disabled: the open session stops working at once.
  const listItem = admin
    .getByRole('list', { name: 'Accounts' })
    .getByRole('listitem')
    .filter({ hasText: email });
  await listItem.getByRole('button', { name: 'Disable' }).click();
  await expect(listItem).toContainText('Disabled');
  expect((await person.request.get('/api/cases')).status()).toBe(401);

  await admin.context().close();
  await person.context().close();
});

test('the audit log records sign-ins and is for administrators only', async ({ browser }) => {
  const admin = await (
    await browser.newContext({ storageState: storageStatePath('admin') })
  ).newPage();
  await admin.goto('/app/admin/audit');
  await expect(admin.getByText(/This is not tamper-proof/)).toBeVisible();
  await admin.getByLabel('Action').selectOption({ label: 'Sign-in and sign-out' });
  await expect(admin.getByRole('cell', { name: 'auth.sign_in' }).first()).toBeVisible();

  const page = await (await admin.request.get('/api/admin/audit?limit=200')).json();
  const body = JSON.stringify(page);
  expect(body).not.toMatch(/password"\s*:/i); // no password fields in any entry

  for (const account of ['advocate', 'paralegal', 'client'] as const) {
    const other = await browser.newContext({ storageState: storageStatePath(account) });
    expect((await other.request.get('/api/admin/audit')).status(), account).toBe(403);
    await other.close();
  }
  await admin.context().close();
});
