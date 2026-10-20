import { expect, test, type Browser, type Page } from '@playwright/test';
import { storageStatePath, type Account } from './support/accounts';

// AI case analysis end to end: the real API, the real worker process and the
// SCRIPTED test provider (scripts/e2e.py sets LEXFLOW_AI_PROVIDER=scripted for
// the e2e database), so no request ever reaches Google. The document is
// invented; the judgments are the SYNTHETIC fixtures imported by `prepare`.
test.describe.configure({ mode: 'serial' });

const SATTVIK = /Sattvik Foods Pvt\. Ltd\. v\./;
const NOTICE = [
  'SYNTHETIC TEST DOCUMENT - invented for LexFlow end-to-end tests.',
  "The plaintiff's registered trade mark SATTVIK has been used on packaged snack foods since 2015.",
  'The defendant began selling snacks under the mark NISARGA SATTVA in 2024, in similar yellow packs.',
].join('\n');

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

test('an advocate analyses a sample case and every claim links to its source', async ({
  browser,
}) => {
  const lead = await signedIn(browser, 'advocate');
  const id = await sattvikId(lead);

  await lead.goto(`/app/cases/${id}?tab=documents`);
  await lead.getByLabel('Choose files to attach').setInputFiles({
    name: 'e2e-analysis-notice.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from(NOTICE),
  });
  const row = lead
    .getByRole('list', { name: 'Case documents' })
    .getByRole('listitem')
    .filter({ hasText: 'e2e-analysis-notice.txt' });
  await expect(row).toContainText('Text extracted', { timeout: 60_000 });

  await lead.getByRole('tab', { name: /AI Analysis/ }).click();
  const notice = lead.getByRole('note', { name: 'What leaves this computer' });
  await expect(notice).toContainText('Scripted test provider (not AI)');
  const analyse = lead.getByRole('button', { name: /Analyse case/ });
  await expect(analyse).toBeDisabled(); // not before the confirmation
  await lead.getByRole('checkbox', { name: /I confirm/ }).check();
  await analyse.click();

  await expect(lead.getByText(/Scripted test output — not AI/)).toBeVisible({ timeout: 60_000 });
  await expect(lead.getByText(/1 item was removed because it could not be verified/)).toBeVisible();
  await expect(lead.getByText(/decision support for the advocate/).first()).toBeVisible();

  // A precedent from the SYNTHETIC collection, labelled, linked to its passage.
  const precedent = lead.getByRole('article', { name: /Golden Grain Foods/ });
  await expect(precedent).toContainText('Synthetic test data');
  const passageLink = precedent.getByRole('link', { name: /Read the passage/ });
  const judgmentHref = await passageLink.getAttribute('href');
  expect(judgmentHref).toMatch(/^\/app\/precedents\/[0-9a-f-]{36}/);

  // Every fact's source link opens the document text it quotes.
  const factLink = lead.getByRole('link', { name: /e2e-analysis-notice\.txt, part 1/ });
  await expect(factLink).toBeVisible();
  await factLink.click();
  await expect(lead.getByText(/registered trade mark SATTVIK/)).toBeVisible();

  await lead.goto(judgmentHref as string);
  await expect(lead.getByRole('heading', { name: /Golden Grain Foods/ })).toBeVisible();
  await lead.context().close();
});

test('a paralegal sees the result but cannot start an analysis', async ({ browser }) => {
  const paralegal = await signedIn(browser, 'paralegal');
  const id = await sattvikId(paralegal);
  await paralegal.goto(`/app/cases/${id}?tab=analysis`);
  const analyse = paralegal.getByRole('button', { name: /Analyse case/ });
  await expect(analyse).toBeDisabled();
  await expect(analyse).toHaveAccessibleDescription(/advocates and administrators/);
  await expect(paralegal.getByText(/Scripted test output — not AI/)).toBeVisible();
  await paralegal.context().close();
});

test('outsiders and clients cannot reach the analysis routes', async ({ browser }) => {
  const outsider = await signedIn(browser, 'outsider');
  const lead = await signedIn(browser, 'advocate');
  const id = await sattvikId(lead);
  expect((await outsider.request.get(`/api/cases/${id}/analysis-runs`)).status()).toBe(404);
  const client = await signedIn(browser, 'client');
  expect((await client.request.get(`/api/cases/${id}/analysis-runs`)).status()).toBe(403);
  for (const page of [outsider, lead, client]) await page.context().close();
});
