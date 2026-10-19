import { expect, test } from '@playwright/test';
import { storageStatePath } from './support/accounts';
import { restartBackend } from './support/backend';

// One story, in order: each test builds on the case the previous one created.
test.describe.configure({ mode: 'serial' });

// Test records are labelled as such; nothing here imitates a real matter.
const TITLE = 'E2E Test Matter v. Example Party';
const NOTES = {
  name: 'e2e-notes.txt',
  mimeType: 'text/plain',
  buffer: Buffer.from('E2E notes.\n'),
};
const BRIEF = {
  name: 'e2e-brief.pdf',
  mimeType: 'application/pdf',
  buffer: Buffer.from('%PDF-1.4\n% end-to-end test file\n%%EOF\n'),
};

let caseUrl = '';

const escape = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// Signed in (by global setup) as the sample lead advocate, Aryan Goyal.
test.use({ storageState: storageStatePath('advocate') });

test.beforeEach(async ({ page }) => {
  await page.goto('/app/cases');
  await expect(page.getByRole('heading', { name: 'Cases' })).toBeVisible();
});

test('the case list comes from the API, with sample cases labelled', async ({ page }) => {
  const cases = (await (await page.request.get('/api/cases')).json()) as Array<{
    title: string;
    isSample: boolean;
  }>;
  expect(cases.length).toBeGreaterThan(0);
  expect(cases.every((c) => c.isSample)).toBe(true);

  // Header row plus one row per case.
  await expect(page.getByRole('row')).toHaveCount(cases.length + 1);
  await expect(page.getByRole('link', { name: new RegExp(escape(cases[0].title)) })).toBeVisible();
  await expect(page.getByText(/Cases marked Sample are fictional/)).toBeVisible();
});

test('a new case is saved on the server and survives a reload', async ({ page }) => {
  await page.getByRole('link', { name: 'New Case' }).first().click();
  await page.getByLabel(/Case Title/).fill(TITLE);
  await page.getByLabel(/Client/).selectOption({ index: 1 });
  await page.getByLabel(/Summary/).fill('Created by the end-to-end tests to check persistence.');
  await page.getByRole('button', { name: 'Create Case' }).click();

  await expect(page).toHaveURL(/\/app\/cases\/[0-9a-f-]{36}\?tab=documents$/);
  await expect(page.getByRole('heading', { level: 1, name: TITLE })).toBeVisible();
  caseUrl = page.url();

  await page.reload();
  await expect(page.getByRole('heading', { level: 1, name: TITLE })).toBeVisible();

  await page.goto('/app/cases');
  const row = page.getByRole('row').filter({ hasText: TITLE });
  await expect(row).toHaveCount(1);
  await expect(row).toContainText(/LF-\d{4}-\d{4,}/); // number allocated by the server
});

test('documents upload, open, persist and delete', async ({ page }) => {
  await page.goto(caseUrl);
  await page.getByLabel('Choose files to attach').setInputFiles([NOTES, BRIEF]);
  await expect(page.getByText('Added 2 documents.')).toBeVisible();

  await page.reload();
  const openNotes = page.getByRole('link', { name: `Open ${NOTES.name}` });
  const openBrief = page.getByRole('link', { name: `Open ${BRIEF.name}` });
  await expect(openNotes).toBeVisible();
  await expect(openBrief).toBeVisible();

  // The stored bytes come back unchanged, with safe headers.
  const notesHref = await openNotes.getAttribute('href');
  const download = await page.request.get(notesHref ?? '');
  expect(download.status()).toBe(200);
  expect(await download.body()).toEqual(NOTES.buffer);
  expect(download.headers()['x-content-type-options']).toBe('nosniff');
  expect(download.headers()['content-disposition']).toContain(`filename*=UTF-8''${NOTES.name}`);

  // Open shows the file in a new tab.
  const [tab] = await Promise.all([page.context().waitForEvent('page'), openNotes.click()]);
  await expect(tab.locator('body')).toContainText('E2E notes.');
  await tab.close();

  // Remove the brief: gone from the case and from downloads, also after a
  // reload, but kept under Deleted Documents (deletion is soft).
  const briefHref = await openBrief.getAttribute('href');
  const live = page.getByRole('list', { name: 'Case documents' });
  const deleted = page.getByRole('list', { name: 'Deleted documents' });
  await page.getByRole('button', { name: `Remove ${BRIEF.name}` }).click();
  await expect(live.getByText(BRIEF.name)).toHaveCount(0);
  expect((await page.request.get(briefHref ?? '')).status()).toBe(404);
  await page.reload();
  await expect(openNotes).toBeVisible();
  await expect(live.getByText(BRIEF.name)).toHaveCount(0);
  await expect(deleted.getByText(BRIEF.name)).toBeVisible();
});

test('the server rejects a file whose contents do not match its type', async ({ page }) => {
  await page.goto(caseUrl);
  // Passes the browser's name checks, so only the server can catch it.
  await page.getByLabel('Choose files to attach').setInputFiles({
    name: 'not-really.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('plain text pretending to be a PDF'),
  });

  await expect(page.getByText('One file was not added:')).toBeVisible();
  await expect(
    page.getByText("The contents of not-really.pdf don't match its file type."),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByRole('link', { name: `Open ${NOTES.name}` })).toBeVisible();
  await expect(page.getByText('not-really.pdf')).toHaveCount(0);
});

test('cases and files are still there after the API restarts', async ({ page }) => {
  await restartBackend();

  await page.goto(caseUrl);
  await expect(page.getByRole('heading', { level: 1, name: TITLE })).toBeVisible();
  const openNotes = page.getByRole('link', { name: `Open ${NOTES.name}` });
  await expect(openNotes).toBeVisible();
  const download = await page.request.get((await openNotes.getAttribute('href')) ?? '');
  expect(await download.body()).toEqual(NOTES.buffer);
});

test('an unknown case shows "Case not found"', async ({ page }) => {
  await page.goto('/app/cases/00000000-0000-4000-8000-000000000000');
  await expect(page.getByRole('heading', { name: 'Case not found' })).toBeVisible();
});
