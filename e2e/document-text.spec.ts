import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test, type Browser, type Page } from '@playwright/test';
import { APP_ORIGIN, storageStatePath, type Account } from './support/accounts';

// Text extraction end to end: the real API, the real worker process (started
// by global setup) and the committed FICTIONAL fixtures in
// server/tests/fixtures/documents/.
test.describe.configure({ mode: 'serial' });

const FIXTURES = fileURLToPath(new URL('../server/tests/fixtures/documents/', import.meta.url));
const CHANGE_HEADERS = { Origin: APP_ORIGIN, 'X-LexFlow-Request': '1' };
const SATTVIK = /Sattvik Foods Pvt\. Ltd\. v\./;

function fixture(name: string) {
  return {
    name: `e2e-${name}`,
    mimeType: name.endsWith('.pdf') ? 'application/pdf' : 'text/plain',
    buffer: readFileSync(path.join(FIXTURES, name)),
  };
}

async function signedIn(browser: Browser, account: Account): Promise<Page> {
  return (await browser.newContext({ storageState: storageStatePath(account) })).newPage();
}

async function sattvikId(page: Page): Promise<string> {
  const cases = (await (await page.request.get('/api/cases')).json()) as Array<{
    id: string;
    title: string;
  }>;
  const found = cases.find((c) => SATTVIK.test(c.title));
  if (!found) throw new Error('the Sattvik sample case is not visible');
  return found.id;
}

test('a 3-page PDF is processed in the background and read page by page', async ({ browser }) => {
  const lead = await signedIn(browser, 'advocate');
  const id = await sattvikId(lead);
  await lead.goto(`/app/cases/${id}?tab=documents`);
  await lead
    .getByLabel('Choose files to attach')
    .setInputFiles(fixture('fictional-petition-3-pages.pdf'));

  const row = lead
    .getByRole('list', { name: 'Case documents' })
    .getByRole('listitem')
    .filter({ hasText: 'e2e-fictional-petition-3-pages.pdf' });
  // The worker picks it up; the page refreshes itself until the text is ready.
  await expect(row).toContainText('Text extracted · 3 pages', { timeout: 60_000 });

  await row.getByRole('link', { name: /View the text of/ }).click();
  await expect(lead.getByRole('article', { name: 'Page 1 of 3' })).toContainText(
    'FICTIONAL TEST DOCUMENT - not a real matter.',
  );
  await lead.getByRole('link', { name: /Next page/ }).click();
  const second = lead.getByRole('article', { name: 'Page 2 of 3' });
  await expect(second).toContainText('Annexure T-1');
  await expect(second).not.toContainText('Page one');

  // The same through the API: page numbers are the PDF's own.
  const documentId = lead.url().split('/documents/')[1].split('/')[0];
  const body = await (await lead.request.get(`/api/documents/${documentId}/text?section=3`)).json();
  expect(body.section.pageNumber).toBe(3);
  expect(body.section.text).toContain('prayer for relief');
  await lead.context().close();
});

test('a PDF without a text layer fails visibly and can be retried', async ({ browser }) => {
  const lead = await signedIn(browser, 'advocate');
  const id = await sattvikId(lead);
  await lead.goto(`/app/cases/${id}?tab=documents`);
  await lead
    .getByLabel('Choose files to attach')
    .setInputFiles(fixture('fictional-scan-no-text.pdf'));
  const row = lead
    .getByRole('list', { name: 'Case documents' })
    .getByRole('listitem')
    .filter({ hasText: 'e2e-fictional-scan-no-text.pdf' });
  await expect(row).toContainText('Text extraction failed: This PDF has no text layer', {
    timeout: 60_000,
  });
  await row.getByRole('button', { name: /Try extracting the text of/ }).click();
  await expect(
    lead.getByText('e2e-fictional-scan-no-text.pdf will be processed again.'),
  ).toBeVisible();
  // Processed again by the worker, with the same honest outcome.
  await expect(row).toContainText('Text extraction failed: This PDF has no text layer', {
    timeout: 60_000,
  });
  await lead.context().close();
});

test('clients and outsiders cannot read extracted text', async ({ browser }) => {
  const lead = await signedIn(browser, 'advocate');
  const id = await sattvikId(lead);
  const detail = await (await lead.request.get(`/api/cases/${id}`)).json();
  const document = detail.documents.find(
    (d: { name: string }) => d.name === 'e2e-fictional-petition-3-pages.pdf',
  );
  expect(document.processing.status).toBe('ready');

  const client = await signedIn(browser, 'client');
  expect((await client.request.get(`/api/documents/${document.id}/text`)).status()).toBe(403);
  const outsider = await signedIn(browser, 'outsider');
  expect((await outsider.request.get(`/api/documents/${document.id}/text`)).status()).toBe(404);

  // Deleted: hidden from everyone, including the lead.
  expect(
    (
      await lead.request.delete(`/api/documents/${document.id}`, { headers: CHANGE_HEADERS })
    ).status(),
  ).toBe(204);
  expect((await lead.request.get(`/api/documents/${document.id}/text`)).status()).toBe(404);
  for (const page of [lead, client, outsider]) await page.context().close();
});
