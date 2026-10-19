import { expect, test } from '@playwright/test';
import { APP_ORIGIN, storageStatePath } from './support/accounts';

// Each role against the real API: what the screens offer, and what the server
// refuses even when the screens are bypassed.

const CHANGE_HEADERS = { Origin: APP_ORIGIN, 'X-LexFlow-Request': '1' };
const SATTVIK = /Sattvik Foods Pvt\. Ltd\. v\./;

test.describe('a Paralegal on the Sattvik case team', () => {
  test.use({ storageState: storageStatePath('paralegal') });

  test('sees only that case, adds a document, and cannot remove one', async ({ page }) => {
    await page.goto('/app/cases');
    await expect(page.getByRole('row')).toHaveCount(2); // header + the one case
    await expect(page.getByRole('link', { name: /New Case/ })).toHaveCount(0);

    await page.getByRole('link', { name: SATTVIK }).click();
    await page.getByRole('tab', { name: /Documents/ }).click();
    await expect(page.getByText('Your access: Paralegal on the case team')).toBeVisible();
    await page.getByLabel('Choose files to attach').setInputFiles({
      name: 'paralegal-note.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('Filed by the paralegal.\n'),
    });
    await expect(page.getByText('Added paralegal-note.txt.')).toBeVisible();
    await expect(page.getByRole('button', { name: /^Remove / })).toHaveCount(0);

    // Going around the screen: the server refuses.
    const caseId = page.url().split('/cases/')[1].split('?')[0];
    const detail = await (await page.request.get(`/api/cases/${caseId}`)).json();
    const note = detail.documents.find((d: { name: string }) => d.name === 'paralegal-note.txt');
    const removal = await page.request.delete(`/api/documents/${note.id}`, {
      headers: CHANGE_HEADERS,
    });
    expect(removal.status()).toBe(403);
    const closing = await page.request.patch(`/api/cases/${caseId}`, {
      headers: CHANGE_HEADERS,
      data: { status: 'Closed' },
    });
    expect(closing.status()).toBe(403);
    expect((await page.request.get(`/api/cases/${caseId}`)).ok()).toBe(true);
  });
});

test.describe('an Advocate who does not work on the Sattvik case', () => {
  test.use({ storageState: storageStatePath('outsider') });

  test('cannot find it, by screen or by API', async ({ page, browser }) => {
    // Learn the case id the way an attacker might: from someone else's view.
    const admin = await browser.newContext({ storageState: storageStatePath('admin') });
    const cases = await (await admin.request.get('/api/cases')).json();
    const sattvik = cases.find((c: { title: string }) => SATTVIK.test(c.title));
    await admin.close();

    await page.goto('/app/cases');
    await expect(page.getByRole('link', { name: SATTVIK })).toHaveCount(0);

    await page.goto(`/app/cases/${sattvik.id}`);
    await expect(page.getByRole('heading', { name: 'Case not found' })).toBeVisible();

    const direct = await page.request.get(`/api/cases/${sattvik.id}`);
    expect(direct.status()).toBe(404);
    const documents = await page.request.get(`/api/cases/${sattvik.id}/documents`);
    expect(documents.status()).toBe(404);
  });
});
