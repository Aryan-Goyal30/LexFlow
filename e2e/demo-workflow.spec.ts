import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { expect, test, type Browser, type Page } from '@playwright/test';
import { storageStatePath, type Account } from './support/accounts';

// Milestone 1: the complete demonstration on a NEW, FICTIONAL case in the
// isolated e2e database (lexflow_e2e_playwright, marked and verified by the server).
// Everything is invented: the client, the case and the documents come from
// the tracked pack in server/tests/fixtures/demo-case/ (see its README); the
// judgments are the SYNTHETIC fixtures; analysis and assessment come from the
// scripted test provider (not AI). No external service is contacted.

test.describe.configure({ mode: 'serial' });

const PACK = fileURLToPath(new URL('../server/tests/fixtures/demo-case/', import.meta.url));
type Manifest = {
  client: { name: string; email: string; phone: string };
  case: { title: string; description: string; courtName: string; opposingParty: string };
  documents: { file: string }[];
  contradiction: { statements: { file: string; page: number | null; text: string }[] };
};

async function signedIn(browser: Browser, account: Account): Promise<Page> {
  return (await browser.newContext({ storageState: storageStatePath(account) })).newPage();
}

async function manifest(): Promise<Manifest> {
  return JSON.parse(await readFile(`${PACK}manifest.json`, 'utf-8')) as Manifest;
}

let caseId = '';

test('a lawyer opens a fictional client and case and files the fictional papers', async ({
  browser,
}) => {
  const pack = await manifest();
  const lead = await signedIn(browser, 'advocate');
  expect((await (await lead.request.get('/api/demo')).json()).verified).toBe(true);

  await lead.goto('/app/clients/new');
  await expect(lead.getByRole('complementary', { name: 'Demo environment' })).toBeVisible();
  await lead.getByRole('checkbox', { name: /Fictional demo client/ }).check();
  await lead.getByLabel(/Name/).fill(pack.client.name);
  await lead.getByLabel(/E-mail/).fill(pack.client.email);
  await lead.getByLabel(/Phone/).fill(pack.client.phone);
  await lead.getByRole('button', { name: 'Add Client' }).click();
  await expect(lead).toHaveURL(/\/app\/cases\/new\?client=/);

  await lead.getByRole('checkbox', { name: /Fictional demo case/ }).check();
  await lead.getByLabel(/Case Title/).fill(pack.case.title);
  await lead.getByLabel('Practice Area').selectOption('Intellectual Property');
  await lead.getByLabel(/Summary/).fill(pack.case.description);
  await lead.getByLabel('Opposing Party').fill(pack.case.opposingParty);
  await lead.getByLabel('Court / Forum').fill(pack.case.courtName);
  await lead.getByRole('button', { name: 'Create Case' }).click();
  await expect(lead).toHaveURL(/\/app\/cases\/[0-9a-f-]{36}\?tab=documents/);
  caseId = new URL(lead.url()).pathname.split('/').pop() as string;
  const created = await (await lead.request.get(`/api/cases/${caseId}`)).json();
  expect(created.isSample).toBe(true); // fictional: the sample flag D1 already accepts

  await lead
    .getByLabel('Choose files to attach')
    .setInputFiles(pack.documents.map((d) => `${PACK}${d.file}`));
  const list = lead.getByRole('list', { name: 'Case documents' });
  for (const { file } of pack.documents) {
    await expect(list.getByRole('listitem').filter({ hasText: file })).toContainText(
      'Text extracted',
      { timeout: 90_000 },
    );
  }
  await lead.context().close();
});

test('the extracted text is page-aware and both sides of the planted contradiction are found', async ({
  browser,
}) => {
  const pack = await manifest();
  const lead = await signedIn(browser, 'advocate');
  const [affidavit, ledger] = pack.contradiction.statements;
  const search = await lead.request.get(
    `/api/cases/${caseId}/search?q=${encodeURIComponent('VF/INV/0001')}&mode=keyword&limit=20`,
  );
  expect(search.status()).toBe(200);
  const hits = (await search.json()).results as {
    documentName: string;
    pageNumber: number | null;
    text: string;
  }[];
  const squash = (s: string) => s.replace(/\s+/g, ' ');
  const affidavitHit = hits.find((h) => h.documentName === affidavit.file);
  expect(affidavitHit?.pageNumber).toBe(affidavit.page); // the page the manifest names
  expect(squash(affidavitHit?.text ?? '')).toContain(affidavit.text);
  const ledgerHit = hits.find((h) => h.documentName === ledger.file);
  expect(ledgerHit?.pageNumber).toBeNull(); // a text file has parts, not pages
  expect(squash(ledgerHit?.text ?? '')).toContain(ledger.text.replace(/\s+/g, ' '));

  // The plaint's second page, read in the app.
  await lead.goto(`/app/cases/${caseId}?tab=documents`);
  const plaint = lead
    .getByRole('list', { name: 'Case documents' })
    .getByRole('listitem')
    .filter({ hasText: '01-plaint.pdf' });
  await plaint.getByRole('link', { name: 'View the text of 01-plaint.pdf' }).click();
  await lead.getByRole('link', { name: /Next page/ }).click();
  await expect(lead.getByText(/a field officer of the plaintiff found millet snack/)).toBeVisible();
  await lead.context().close();
});

test('analyse, review (accept, edit, reject), export the brief and assess the fictional case', async ({
  browser,
}) => {
  const lead = await signedIn(browser, 'advocate');
  await lead.goto(`/app/cases/${caseId}?tab=analysis`);
  await expect(lead.getByRole('note', { name: 'What leaves this computer' })).toContainText(
    'Scripted test provider (not AI)',
  );
  await lead.getByRole('checkbox', { name: /I confirm/ }).check();
  await lead.getByRole('button', { name: /Analyse case/ }).click();
  await expect(lead.getByText(/Scripted test output — not AI/)).toBeVisible({ timeout: 90_000 });
  // The scripted double's invented fact was removed by validation.
  await expect(lead.getByText(/1 item was removed because it could not be verified/)).toBeVisible();
  // A fact's source link opens the document page it quotes.
  await expect(lead.getByRole('link', { name: /01-plaint\.pdf, page 1/ }).first()).toBeVisible();
  // A SYNTHETIC precedent was retrieved and labelled.
  const firstPrecedent = lead.getByRole('article').first();
  await expect(firstPrecedent).toContainText('Synthetic test data');

  const fact1 = lead.getByRole('region', { name: 'Review of Fact F1' });
  await fact1.getByRole('button', { name: 'Accept' }).click();
  await expect(fact1.getByText('Accepted', { exact: true })).toBeVisible();

  const fact2 = lead.getByRole('region', { name: 'Review of Fact F2' });
  await fact2.getByRole('button', { name: 'Edit wording' }).click();
  await fact2
    .getByLabel(/Lawyer’s wording for Fact F2/)
    .fill('FICTIONAL: the affidavit dates invoice VF/INV/0001 to 14 March 2016 (lawyer wording).');
  await fact2.getByRole('button', { name: 'Save wording' }).click();
  await expect(fact2.getByText('Edited by lawyer')).toBeVisible();

  const contradiction = lead.getByRole('region', { name: 'Review of Contradiction C1' });
  await contradiction.getByRole('button', { name: 'Reject' }).click();
  await contradiction.getByRole('button', { name: 'Reject finding' }).click();
  await expect(contradiction.getByText('Rejected', { exact: true })).toBeVisible();
  await fact2.getByRole('button', { name: 'Show history' }).click();
  await expect(fact2.getByRole('list', { name: /History of F2/ })).toContainText(
    'Accepted with edits',
  );

  const precedent = lead.getByRole('region', { name: 'Review of Precedent comparison P1' });
  await precedent.getByRole('button', { name: 'Accept' }).click();
  await expect(precedent.getByText('Accepted', { exact: true })).toBeVisible();

  const downloading = lead.waitForEvent('download');
  await lead.getByRole('button', { name: 'Export case brief (DOCX)' }).click();
  const bytes = await readFile(await (await downloading).path());
  expect(bytes.subarray(0, 2).toString()).toBe('PK');

  const panel = lead.getByRole('region', { name: 'Outcome assessment (decision support)' });
  await panel.getByRole('button', { name: 'Generate assessment' }).click();
  const view = panel.getByRole('region', { name: /Assessment of/ });
  await expect(view.getByRole('note', { name: 'Demonstration on synthetic data' })).toBeVisible();
  await expect(view.getByText('(a category, not a probability)')).toBeVisible();
  await expect(view).not.toContainText(/\d\s*%|probability of|chance of winning/i);
  const review = view.getByRole('region', { name: 'Lawyer review of this assessment' });
  await review.getByRole('button', { name: 'Accept assessment' }).click();
  await expect(review.getByText('Accepted', { exact: true })).toBeVisible();
  await lead.context().close();
});

test('people outside the fictional case cannot reach it', async ({ browser }) => {
  const outsider = await signedIn(browser, 'outsider');
  expect((await outsider.request.get(`/api/cases/${caseId}`)).status()).toBe(404);
  const paralegal = await signedIn(browser, 'paralegal'); // not on this case's team
  expect((await paralegal.request.get(`/api/cases/${caseId}/analysis-runs`)).status()).toBe(404);
  const client = await signedIn(browser, 'client');
  expect((await client.request.get(`/api/cases/${caseId}`)).status()).toBe(403);
  for (const page of [outsider, paralegal, client]) await page.context().close();
});
