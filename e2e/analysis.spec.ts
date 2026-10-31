import { readFile } from 'node:fs/promises';
import { expect, test, type Browser, type Page } from '@playwright/test';
import { storageStatePath, type Account } from './support/accounts';

/** The analysis shows one section at a time: select the one the next assertions are about. */
const openSection = (page: Page, name: RegExp) =>
  page
    .getByRole('navigation', { name: 'Sections of this analysis' })
    .getByRole('button', { name })
    .click({ timeout: 60_000 }); // the analysis may still be loading

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
  await openSection(lead, /^Precedents/);
  const precedent = lead.getByRole('article', { name: /Golden Grain Foods/ });
  await expect(precedent).toContainText('Synthetic test data');
  const passageLink = precedent.getByRole('link', { name: /Read the passage/ });
  const judgmentHref = await passageLink.getAttribute('href');
  expect(judgmentHref).toMatch(/^\/app\/precedents\/[0-9a-f-]{36}/);

  // Every fact's source link opens the document text it quotes.
  await openSection(lead, /^Key facts/);
  const factLink = lead.getByRole('link', { name: /e2e-analysis-notice\.txt, part 1/ });
  await expect(factLink).toBeVisible();
  await factLink.click();
  await expect(lead.getByText(/registered trade mark SATTVIK/)).toBeVisible();

  await lead.goto(judgmentHref as string);
  await expect(lead.getByRole('heading', { name: /Golden Grain Foods/ })).toBeVisible();
  await lead.context().close();
});

test('a lawyer reviews the findings and exports a brief of the accepted ones (Phase 6)', async ({
  browser,
}) => {
  const lead = await signedIn(browser, 'advocate');
  const id = await sattvikId(lead);
  await lead.goto(`/app/cases/${id}?tab=analysis`);
  await expect(lead.getByText(/Lawyer review: 0 of \d+ findings reviewed/)).toBeVisible({
    timeout: 60_000,
  });
  const fact = lead.getByRole('region', { name: 'Review of Fact F1' });
  await expect(fact.getByText('Unreviewed')).toBeVisible();
  const exportButton = lead.getByRole('button', { name: 'Export case brief (DOCX)' });
  await expect(exportButton).toBeDisabled(); // nothing accepted yet

  await fact.getByRole('button', { name: 'Accept' }).click();
  await expect(fact.getByText('Accepted', { exact: true })).toBeVisible();

  await openSection(lead, /^Precedents/);
  const precedent = lead.getByRole('region', { name: 'Review of Precedent comparison P1' });
  await precedent.getByRole('button', { name: 'Edit wording' }).click();
  const wording = 'SYNTHETIC: the precedent weighs prior use (lawyer’s wording, e2e).';
  await precedent.getByLabel(/Lawyer’s wording for Precedent comparison P1/).fill(wording);
  await precedent.getByRole('button', { name: 'Save wording' }).click();
  await expect(precedent.getByText('Edited by lawyer')).toBeVisible();
  await expect(precedent.getByText(wording)).toBeVisible();

  await expect(exportButton).toBeEnabled();
  const downloading = lead.waitForEvent('download');
  await exportButton.click();
  const download = await downloading;
  expect(download.suggestedFilename()).toMatch(/^case-brief-LF-[\w-]+\.docx$/);
  const bytes = await readFile(await download.path());
  expect(bytes.subarray(0, 2).toString()).toBe('PK'); // a Word (zip) package
  await expect(lead.getByText(/Brief saved as case-brief-LF-/)).toBeVisible();

  // The decisions are on the matter timeline (never sent to the model).
  await lead.goto(`/app/cases/${id}?tab=overview`);
  await expect(lead.getByText('Lawyer review').first()).toBeVisible();
  await expect(lead.getByText(/Fact F1 of the AI analysis of .* accepted\./)).toBeVisible();
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
  // The lawyer's decisions are visible, the review controls are not.
  const fact = paralegal.getByRole('region', { name: 'Review of Fact F1' });
  await expect(fact.getByText('Accepted', { exact: true })).toBeVisible();
  await expect(fact.getByRole('button', { name: 'Accept' })).toHaveCount(0);
  await expect(fact.getByRole('button', { name: 'Edit wording' })).toHaveCount(0);
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

test('the outcome assessment demo: generated from accepted findings, labelled, reviewed (Phase 7)', async ({
  browser,
}) => {
  // F1 was accepted and P1 accepted with the lawyer's wording in the Phase 6 test above.
  const lead = await signedIn(browser, 'advocate');
  const id = await sattvikId(lead);
  await lead.goto(`/app/cases/${id}?tab=analysis`);
  await openSection(lead, /^Outcome assessment/);
  const panel = lead.getByRole('region', { name: 'Outcome assessment (decision support)' });
  await expect(panel.getByText(/Decision support, not a prediction/)).toBeVisible({
    timeout: 60_000,
  });
  await expect(
    panel.getByText(/Uses \d+ accepted findings? and 1 accepted precedent/),
  ).toBeVisible();
  await panel.getByRole('button', { name: 'Generate assessment' }).click();

  const view = panel.getByRole('region', { name: /Assessment of/ });
  await expect(view.getByRole('note', { name: 'Demonstration on synthetic data' })).toBeVisible();
  await expect(view.getByText('(a category, not a probability)')).toBeVisible();
  await expect(view.getByText('Limited support')).toBeVisible();
  await expect(view.getByText('Supports', { exact: true })).toBeVisible();
  await expect(view.getByText('Synthetic test data')).toBeVisible();
  await expect(view.getByText(/\[Scripted\] Demonstration assessment/)).toBeVisible();
  // The scripted double's invented precedent and unsupported step were removed.
  await expect(view.getByText(/2 items were removed by the server/)).toBeVisible();
  await expect(view).not.toContainText(/\d\s*%|probability of|chance of winning/i);
  const passage = view.getByRole('link', { name: /Read the passage/ });
  await expect(passage).toHaveAttribute('href', /\/app\/precedents\//);

  const review = view.getByRole('region', { name: 'Lawyer review of this assessment' });
  await expect(review.getByText(/Not yet reviewed: this is not a lawyer/)).toBeVisible();
  await review.getByRole('button', { name: 'Accept assessment' }).click();
  await expect(review.getByText('Accepted', { exact: true })).toBeVisible();

  // The brief (checked in detail by the server tests, which open the DOCX) still exports.
  const downloading = lead.waitForEvent('download');
  await lead.getByRole('button', { name: 'Export case brief (DOCX)' }).click();
  const bytes = await readFile(await (await downloading).path());
  expect(bytes.subarray(0, 2).toString()).toBe('PK');

  // Read-only for a paralegal; unreachable for outsiders and clients.
  const paralegal = await signedIn(browser, 'paralegal');
  await paralegal.goto(`/app/cases/${id}?tab=analysis`);
  await openSection(paralegal, /^Outcome assessment/);
  const readOnly = paralegal.getByRole('region', { name: 'Outcome assessment (decision support)' });
  await expect(readOnly.getByText('Accepted', { exact: true })).toBeVisible({ timeout: 60_000 });
  await expect(readOnly.getByRole('button', { name: 'Generate assessment' })).toBeDisabled();
  await expect(readOnly.getByRole('button', { name: 'Accept assessment' })).toHaveCount(0);
  const runs = await (await lead.request.get(`/api/cases/${id}/analysis-runs`)).json();
  const assessments = `/api/cases/${id}/analysis-runs/${runs.items[0].id}/assessments`;
  const outsider = await signedIn(browser, 'outsider');
  expect((await outsider.request.get(assessments)).status()).toBe(404);
  const client = await signedIn(browser, 'client');
  expect((await client.request.get(assessments)).status()).toBe(403);
  for (const page of [lead, paralegal, outsider, client]) await page.context().close();
});
