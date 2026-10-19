import { expect, test, type Browser, type Page } from '@playwright/test';
import { APP_ORIGIN, storageStatePath, type Account } from './support/accounts';

// Editing, archiving and case teams against the real API and database. Each
// test puts the Sattvik sample case back as it found it, so the other specs
// see the same data whatever order they run in.
test.describe.configure({ mode: 'serial' });

const CHANGE_HEADERS = { Origin: APP_ORIGIN, 'X-LexFlow-Request': '1' };
const SATTVIK = /Sattvik Foods Pvt\. Ltd\. v\./;

async function signedIn(browser: Browser, account: Account): Promise<Page> {
  const context = await browser.newContext({ storageState: storageStatePath(account) });
  return context.newPage();
}

async function sattvikId(page: Page): Promise<string> {
  const cases = (await (await page.request.get('/api/cases?archived=include')).json()) as Array<{
    id: string;
    title: string;
  }>;
  const found = cases.find((c) => SATTVIK.test(c.title));
  if (!found) throw new Error('the Sattvik sample case is not visible');
  return found.id;
}

test('the lead edits the case, and the timeline records who did it', async ({ browser }) => {
  const page = await signedIn(browser, 'advocate');
  const id = await sattvikId(page);
  const before = await (await page.request.get(`/api/cases/${id}`)).json();

  await page.goto(`/app/cases/${id}`);
  await page.getByRole('link', { name: 'Edit case' }).click();
  await page.getByLabel('Priority').selectOption('Critical');
  await page.getByLabel('Status').selectOption('On Hold');
  await page.getByRole('button', { name: 'Save Changes' }).click();

  await expect(page).toHaveURL(new RegExp(`/app/cases/${id}$`));
  const entry = page.getByRole('listitem').filter({ hasText: 'Case details updated' }).last();
  await expect(entry).toContainText(`Status changed from ${before.status} to On Hold.`);
  await expect(entry).toContainText('Priority changed from');
  await expect(entry).toContainText('Aryan Goyal');

  // Survives a reload: it is on the server.
  await page.reload();
  await expect(page.getByText('On Hold').first()).toBeVisible();

  // Put it back.
  const restored = await page.request.patch(`/api/cases/${id}`, {
    headers: CHANGE_HEADERS,
    data: { status: before.status, priority: before.priority },
  });
  expect(restored.status()).toBe(200);
  await page.context().close();
});

test('a paralegal may change the court but not the title', async ({ browser }) => {
  const page = await signedIn(browser, 'paralegal');
  const id = await sattvikId(page);
  const before = await (await page.request.get(`/api/cases/${id}`)).json();

  await page.goto(`/app/cases/${id}/edit`);
  await expect(page.getByLabel('Court / Forum')).toBeVisible();
  await expect(page.getByLabel(/Case Title/)).toHaveCount(0);

  const title = await page.request.patch(`/api/cases/${id}`, {
    headers: CHANGE_HEADERS,
    data: { title: 'Renamed by a paralegal' },
  });
  expect(title.status()).toBe(403);
  expect((await title.json()).code).toBe('field-not-permitted');

  const court = await page.request.patch(`/api/cases/${id}`, {
    headers: CHANGE_HEADERS,
    data: { courtName: 'E2E Test Court' },
  });
  expect(court.status()).toBe(200);
  const putBack = await page.request.patch(`/api/cases/${id}`, {
    headers: CHANGE_HEADERS,
    data: { courtName: before.courtName },
  });
  expect(putBack.status()).toBe(200);
  await page.context().close();
});

test('an archived case is read-only for everyone until restored', async ({ browser }) => {
  const admin = await signedIn(browser, 'admin');
  const lead = await signedIn(browser, 'advocate');
  const id = await sattvikId(admin);

  await admin.goto(`/app/cases/${id}`);
  await admin.getByRole('button', { name: 'Archive case' }).click();
  await admin
    .getByRole('group', { name: /Archive this case\?/ })
    .getByRole('button', {
      name: 'Archive',
    })
    .click();
  await expect(admin.getByText(/^Archived on /)).toBeVisible();

  // The lead still reads it, but nothing changes, even through the API.
  await lead.goto(`/app/cases/${id}`);
  await expect(lead.getByText(/This case is read-only/)).toBeVisible();
  await expect(lead.getByRole('link', { name: 'Edit case' })).toHaveCount(0);
  const edit = await lead.request.patch(`/api/cases/${id}`, {
    headers: CHANGE_HEADERS,
    data: { status: 'Closed' },
  });
  expect(edit.status()).toBe(409);
  expect((await edit.json()).code).toBe('case-archived');

  // Out of the default list, back with "Show archived".
  await lead.goto('/app/cases');
  await expect(lead.getByRole('heading', { name: 'Cases' })).toBeVisible();
  await expect(lead.getByRole('link', { name: SATTVIK })).toHaveCount(0);
  await lead.getByLabel('Show archived').check();
  await expect(lead.getByRole('link', { name: SATTVIK })).toBeVisible();

  // Only an Administrator restores.
  const leadRestore = await lead.request.post(`/api/cases/${id}/unarchive`, {
    headers: CHANGE_HEADERS,
  });
  expect(leadRestore.status()).toBe(403);
  await admin.getByRole('button', { name: 'Restore case' }).click();
  await expect(admin.getByText(/^Archived on /)).toHaveCount(0);
  await expect(admin.getByRole('link', { name: 'Edit case' })).toBeVisible();

  await admin.context().close();
  await lead.context().close();
});

test('adding someone to the team gives them the case; removing takes it away', async ({
  browser,
}) => {
  const lead = await signedIn(browser, 'advocate');
  const outsider = await signedIn(browser, 'outsider');
  const id = await sattvikId(lead);
  expect((await outsider.request.get(`/api/cases/${id}`)).status()).toBe(404);

  await lead.goto(`/app/cases/${id}`);
  await lead.getByLabel('Add to the team').selectOption({ label: 'Rajat Deshpande (advocate)' });
  await lead.getByRole('button', { name: 'Add', exact: true }).click();
  const team = lead.getByRole('list', { name: 'Case team' });
  await expect(team.getByText('Rajat Deshpande')).toBeVisible();

  await outsider.goto(`/app/cases/${id}`);
  await expect(
    outsider.getByText('Your access: Associate advocate on the case team'),
  ).toBeVisible();
  // An associate cannot change the team.
  const detail = await (await outsider.request.get(`/api/cases/${id}`)).json();
  const paralegal = detail.team.find((m: { name: string }) => m.name === 'E2E Paralegal');
  const removal = await outsider.request.delete(`/api/cases/${id}/team/${paralegal.id}`, {
    headers: CHANGE_HEADERS,
  });
  expect(removal.status()).toBe(403);

  await lead.getByRole('button', { name: 'Remove Rajat Deshpande from the case team' }).click();
  await expect(team.getByText('Rajat Deshpande')).toHaveCount(0);
  expect((await outsider.request.get(`/api/cases/${id}`)).status()).toBe(404);

  await lead.context().close();
  await outsider.context().close();
});

test('a deleted document is kept and the lead can restore it, file and all', async ({
  browser,
}) => {
  const lead = await signedIn(browser, 'advocate');
  const id = await sattvikId(lead);
  const content = Buffer.from('E2E restore check.\n');

  await lead.goto(`/app/cases/${id}?tab=documents`);
  await lead.getByLabel('Choose files to attach').setInputFiles({
    name: 'e2e-restore.txt',
    mimeType: 'text/plain',
    buffer: content,
  });
  const live = lead.getByRole('list', { name: 'Case documents' });
  await expect(live.getByText('e2e-restore.txt')).toBeVisible();
  await expect(live.getByText(/added by Aryan Goyal/).first()).toBeVisible();

  await lead.getByRole('button', { name: 'Remove e2e-restore.txt' }).click();
  await expect(live.getByText('e2e-restore.txt')).toHaveCount(0);
  const deleted = lead.getByRole('list', { name: 'Deleted documents' });
  await expect(deleted.getByText('e2e-restore.txt')).toBeVisible();

  // Gone from the API too, until restored.
  const listing = await (await lead.request.get(`/api/cases/${id}/documents/deleted`)).json();
  const removed = listing.find((d: { name: string }) => d.name === 'e2e-restore.txt');
  expect((await lead.request.get(removed.downloadUrl)).status()).toBe(404);

  await deleted.getByRole('button', { name: 'Restore e2e-restore.txt' }).click();
  await expect(live.getByText('e2e-restore.txt')).toBeVisible();
  const download = await lead.request.get(removed.downloadUrl);
  expect(download.status()).toBe(200);
  expect(Buffer.from(await download.body()).equals(content)).toBe(true);
  await lead.context().close();
});

test('a paralegal schedules, changes and cancels a hearing', async ({ browser }) => {
  const page = await signedIn(browser, 'paralegal');
  const id = await sattvikId(page);
  const inTwoWeeks = new Date(Date.now() + 14 * 24 * 3600 * 1000).toISOString().slice(0, 10);

  await page.goto(`/app/cases/${id}`);
  await page.getByRole('button', { name: 'Schedule hearing' }).click();
  const form = page.getByRole('form', { name: 'Schedule a hearing' });
  await form.getByLabel(/^Date/).fill(inTwoWeeks);
  await form.getByLabel('Time').fill('11:15');
  await form.getByLabel(/Court \/ Forum/).fill('E2E Test Court, Room 1');
  await form.getByLabel(/Purpose/).fill('E2E listing');
  await form.getByRole('button', { name: 'Schedule' }).click();

  const hearings = page.getByRole('list', { name: 'Hearings' });
  const item = hearings.getByRole('listitem').filter({ hasText: 'E2E listing' });
  await expect(item).toContainText('11:15 · E2E Test Court, Room 1');
  const detail = await (await page.request.get(`/api/cases/${id}`)).json();
  expect(detail.nextHearing).toBe(inTwoWeeks);

  await item.getByRole('button', { name: 'Change hearing: E2E listing' }).click();
  const edit = page.getByRole('form', { name: 'Change hearing: E2E listing' });
  await edit.getByLabel('Time').fill('');
  await edit.getByRole('button', { name: 'Save' }).click();
  await expect(item).toContainText('time to be confirmed');

  await item.getByRole('button', { name: 'Cancel hearing: E2E listing' }).click();
  await page.getByLabel('Reason (optional)').fill('E2E: adjourned by consent.');
  await page.getByRole('button', { name: 'Cancel hearing', exact: true }).click();
  await expect(item).toContainText('Cancelled · E2E: adjourned by consent.');

  // Kept, but no longer the next or an upcoming hearing.
  const after = await (await page.request.get(`/api/cases/${id}`)).json();
  expect(after.nextHearing).not.toBe(inTwoWeeks);
  const upcoming = await (await page.request.get('/api/hearings/upcoming?limit=50')).json();
  expect(upcoming.map((h: { purpose: string }) => h.purpose)).not.toContain('E2E listing');
  await page.context().close();
});

test('an administrator adds a client and opens their first case', async ({ browser }) => {
  // Led by Rajat Deshpande, so the advocate's case list used by other specs is unchanged.
  const admin = await signedIn(browser, 'admin');
  await admin.goto('/app/clients');
  await admin.getByRole('link', { name: /New Client/ }).click();
  await admin.getByLabel(/Name/).fill('E2E Test Client LLP');
  await admin.getByLabel(/E-mail/).fill('e2e.client@client.example');
  await admin.getByLabel(/Phone/).fill('+91 00000 33333');
  await admin.getByRole('button', { name: 'Add Client' }).click();
  await expect(admin.getByText('Added E2E Test Client LLP.')).toBeVisible();
  const clientUrl = admin.url();

  await admin.getByRole('link', { name: 'Open a case' }).click();
  await expect(admin.getByLabel(/Client/)).toHaveValue(/.+/);
  await admin.getByLabel(/Case Title/).fill('E2E Test Client LLP v. Example Party');
  await admin.getByLabel('Lead Advocate').selectOption({ label: 'Rajat Deshpande' });
  await admin.getByLabel(/Summary/).fill('Opened by the end-to-end tests for a new client.');
  await admin.getByRole('button', { name: 'Create Case' }).click();
  await expect(
    admin.getByRole('heading', { level: 1, name: 'E2E Test Client LLP v. Example Party' }),
  ).toBeVisible();

  await admin.goto(clientUrl);
  await expect(admin.getByRole('list', { name: "Client's cases" }).getByRole('link')).toHaveText(
    'E2E Test Client LLP v. Example Party',
  );

  // Another advocate cannot read this client's details.
  const clientId = clientUrl.split('/clients/')[1];
  const advocate = await signedIn(browser, 'advocate');
  expect((await advocate.request.get(`/api/clients/${clientId}`)).status()).toBe(404);
  await admin.context().close();
  await advocate.context().close();
});

test('the Hearings page lists only the hearings of your cases', async ({ browser }) => {
  const paralegal = await signedIn(browser, 'paralegal');
  const outsider = await signedIn(browser, 'outsider');
  const id = await sattvikId(paralegal);
  const inTenDays = new Date(Date.now() + 10 * 24 * 3600 * 1000).toISOString().slice(0, 10);
  const created = await paralegal.request.post(`/api/cases/${id}/hearings`, {
    headers: CHANGE_HEADERS,
    data: { date: inTenDays, time: '14:00', court: 'E2E Court', purpose: 'E2E schedule check' },
  });
  expect(created.status()).toBe(201);
  const hearingId = (await created.json()).hearings.find(
    (h: { purpose: string }) => h.purpose === 'E2E schedule check',
  ).id;

  await paralegal.goto('/app/hearings');
  const entry = paralegal.getByRole('listitem').filter({ hasText: 'E2E schedule check' });
  await expect(entry).toContainText('14:00');
  await expect(entry.getByRole('link', { name: SATTVIK })).toBeVisible();

  await outsider.goto('/app/hearings');
  await expect(outsider.getByRole('heading', { name: 'Hearings' })).toBeVisible();
  await expect(outsider.getByText('E2E schedule check')).toHaveCount(0);

  // Leave the case as it was: cancelled hearings never show as upcoming.
  const cancelled = await paralegal.request.post(`/api/hearings/${hearingId}/cancel`, {
    headers: CHANGE_HEADERS,
    data: {},
  });
  expect(cancelled.status()).toBe(200);
  await paralegal.context().close();
  await outsider.context().close();
});
