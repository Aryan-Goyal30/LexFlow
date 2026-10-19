import { expect, test } from '@playwright/test';
import { APP_ORIGIN, storageStatePath } from './support/accounts';

// The client portal against the real API: a Client account sees its own case
// and exactly the documents an advocate shared, and nothing of the staff app.

const CHANGE_HEADERS = { Origin: APP_ORIGIN, 'X-LexFlow-Request': '1' };
const SATTVIK = /Sattvik Foods Pvt\. Ltd\. v\./;

test('a shared document reaches the client, and leaves when unshared', async ({ browser }) => {
  const lead = await (
    await browser.newContext({ storageState: storageStatePath('advocate') })
  ).newPage();
  const client = await (
    await browser.newContext({ storageState: storageStatePath('client') })
  ).newPage();

  const cases = await (await lead.request.get('/api/cases')).json();
  const sattvik = cases.find((c: { title: string }) => SATTVIK.test(c.title));
  const content = Buffer.from('Advice for the client.\n');
  const upload = await lead.request.post(`/api/cases/${sattvik.id}/documents`, {
    headers: CHANGE_HEADERS,
    multipart: { file: { name: 'e2e-client-advice.txt', mimeType: 'text/plain', buffer: content } },
  });
  expect(upload.status()).toBe(201);
  const document = await upload.json();

  // Not shared yet: the portal shows nothing and the file cannot be fetched.
  await client.goto('/portal');
  await client.getByRole('link', { name: SATTVIK }).click();
  await expect(client.getByText('No documents have been shared with you yet.')).toBeVisible();
  const portalUrl = `/api/portal/documents/${document.id}/download`;
  expect((await client.request.get(portalUrl)).status()).toBe(404);

  // The lead shares it from the case workspace.
  await lead.goto(`/app/cases/${sattvik.id}?tab=documents`);
  await lead.getByRole('button', { name: 'Share e2e-client-advice.txt with the client' }).click();
  await expect(lead.getByText(/Shared e2e-client-advice.txt with the client/)).toBeVisible();

  await client.reload();
  const shared = client.getByRole('list', { name: 'Shared documents' });
  await expect(shared.getByText('e2e-client-advice.txt')).toBeVisible();
  const download = await client.request.get(portalUrl);
  expect(download.status()).toBe(200);
  expect(Buffer.from(await download.body()).equals(content)).toBe(true);

  // Unshared: gone at once.
  await lead
    .getByRole('button', { name: 'Stop sharing e2e-client-advice.txt with the client' })
    .click();
  await expect(lead.getByText(/Stopped sharing e2e-client-advice.txt/)).toBeVisible();
  expect((await client.request.get(portalUrl)).status()).toBe(404);

  await lead.context().close();
  await client.context().close();
});

test('a client account reaches nothing of the staff app', async ({ browser }) => {
  const client = await (
    await browser.newContext({ storageState: storageStatePath('client') })
  ).newPage();
  for (const path of ['/api/cases', '/api/clients', '/api/hearings', '/api/staff']) {
    const response = await client.request.get(path);
    expect(response.status(), path).toBe(403);
  }
  await client.goto('/app/cases');
  await expect(client).toHaveURL(/\/portal$/);
  await expect(client.getByRole('heading', { name: 'Your Cases' })).toBeVisible();
  await client.context().close();
});
