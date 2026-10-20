import { expect, test, type Browser, type Page } from '@playwright/test';
import { APP_ORIGIN, storageStatePath, type Account } from './support/accounts';

// Phase 4 end to end: the real API, the e2e database and the SYNTHETIC
// judgment fixtures that `scripts/e2e.py prepare` imports through the real
// importer. Embeddings are off in the e2e environment, so only keyword search
// is available (and the UI must say so).
test.describe.configure({ mode: 'serial' });

const SATTVIK = /Sattvik Foods Pvt\. Ltd\. v\./;
const CHANGE_HEADERS = { Origin: APP_ORIGIN, 'X-LexFlow-Request': '1' };
const TRADEMARK = 'Golden Grain Foods v. Sunrise Bakers (SYNTHETIC)';

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

test('research from a case finds a judgment and opens it with its source', async ({ browser }) => {
  const lead = await signedIn(browser, 'advocate');
  await lead.goto(`/app/cases/${await sattvikId(lead)}?tab=research`);
  await expect(lead.getByText(/13 judgments in the collection \(13 synthetic/)).toBeVisible();

  // Embeddings are off here: meaning-based modes are offered as unavailable.
  await expect(
    lead.getByRole('option', { name: /Meaning \(semantic\) \(unavailable\)/ }),
  ).toBeDisabled();
  await expect(lead.getByText(/Searching by meaning is unavailable/)).toBeVisible();

  // Keyboard only: focus the box, type, press Enter.
  const box = lead.getByRole('searchbox', { name: 'Search precedents' });
  await box.focus();
  await lead.keyboard.type('deceptively similar');
  await lead.keyboard.press('Enter');
  await expect(lead.getByText(/1 judgment matched “deceptively similar” · Keywords/)).toBeVisible();

  const card = lead.getByRole('article', { name: TRADEMARK });
  await expect(card).toContainText('deceptively similar');
  await expect(card).toContainText('Synthetic test data');
  await expect(card).toContainText('(SYN) 2018 TEST 103');
  const source = card.getByRole('link', { name: /View at source/ });
  await expect(source).toHaveAttribute('href', 'https://judgments.lexflow.invalid/syn-003');
  await expect(source).toHaveAttribute('rel', 'noopener noreferrer');
  await expect(source).toHaveAttribute('target', '_blank');

  await card.getByRole('link', { name: `Read ${TRADEMARK}` }).click();
  await expect(lead).toHaveURL(/\/app\/precedents\/[0-9a-f-]{36}$/);
  await expect(lead.getByRole('heading', { name: /Golden Grain Foods/ })).toBeVisible();
  await expect(lead.getByRole('alert')).toContainText('Synthetic test data');
  await expect(
    lead.getByText('Invented for automated tests only. Not real judgments; never cite.'),
  ).toBeVisible();
  await expect(lead.getByRole('article', { name: 'Part 1 of 1' })).toContainText(
    'interim injunction',
  );
  await lead.context().close();
});

test('empty and unmatched searches are handled, and a failed search can be retried', async ({
  browser,
}) => {
  const lead = await signedIn(browser, 'advocate');
  await lead.goto('/app/precedents');
  const box = lead.getByRole('searchbox', { name: 'Search the judgment collection' });
  await lead.getByRole('button', { name: 'Search' }).click();
  await expect(lead.getByRole('alert')).toHaveText('Type something to search for.');

  await box.fill('maritime salvage spaceship');
  await lead.getByRole('button', { name: 'Search' }).click();
  await expect(lead.getByText('No judgments matched “maritime salvage spaceship”.')).toBeVisible();

  // The API fails once: an error with a retry, then the real answer.
  let failures = 1;
  await lead.route('**/api/judgments/search?*', (route) =>
    failures-- > 0
      ? route.fulfill({
          status: 503,
          contentType: 'application/problem+json',
          body: JSON.stringify({ status: 503, title: 'Unavailable', detail: 'Try again shortly.' }),
        })
      : route.continue(),
  );
  await box.fill('bail');
  await lead.getByRole('button', { name: 'Search' }).click();
  await expect(lead.getByText('The search did not work')).toBeVisible();
  await lead.getByRole('button', { name: 'Try again' }).click();
  await expect(lead.getByText(/2 judgments matched “bail”/)).toBeVisible();
  await lead.context().close();
});

test('the Precedent Library browses, filters and pages the collection', async ({ browser }) => {
  const paralegal = await signedIn(browser, 'paralegal');
  await paralegal.goto('/app/cases');
  await paralegal.getByRole('link', { name: 'Precedent Library' }).click();
  await expect(paralegal.getByText('13 judgments, newest first.')).toBeVisible();
  await expect(paralegal.getByRole('note')).toContainText(
    'Every judgment here is synthetic test data',
  );

  await paralegal.getByLabel('Court').selectOption('SYNTHETIC District Court (test fixture)');
  await paralegal.getByRole('button', { name: 'Apply filters' }).click();
  await expect(paralegal.getByText('5 judgments, newest first.')).toBeVisible();
  await expect(paralegal).toHaveURL(/court=SYNTHETIC\+District/);

  await paralegal.getByRole('button', { name: 'Clear' }).click();
  await paralegal.getByRole('searchbox').fill('court held');
  await paralegal.getByRole('button', { name: 'Search' }).click();
  await expect(paralegal.getByText('Page 1 of 2')).toBeVisible();
  const first = await paralegal.getByRole('article').first().getAttribute('aria-label');
  await paralegal.getByRole('button', { name: /Next/ }).click();
  await expect(paralegal.getByText('Page 2 of 2')).toBeVisible();
  await expect(paralegal).toHaveURL(/page=2/);
  expect(await paralegal.getByRole('article').first().getAttribute('aria-label')).not.toBe(first);
  await paralegal.context().close();
});

test('the library works at phone width without sideways scrolling', async ({ browser }) => {
  const lead = await signedIn(browser, 'advocate');
  await lead.setViewportSize({ width: 375, height: 760 });
  await lead.goto('/app/precedents?q=notice');
  await expect(lead.getByRole('article').first()).toBeVisible();
  const overflow = await lead.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
  await lead.context().close();
});

test('clients and anonymous callers cannot reach the collection', async ({
  browser,
  playwright,
}) => {
  const client = await signedIn(browser, 'client');
  for (const path of ['/api/judgments', '/api/judgments/facets', '/api/judgments/search?q=bail']) {
    expect((await client.request.get(path)).status()).toBe(403);
  }
  await client.context().close();
  const anonymous = await playwright.request.newContext({ baseURL: APP_ORIGIN });
  expect((await anonymous.get('/api/judgments/search?q=bail')).status()).toBe(401);
  await anonymous.dispose();
});

test('a private case document never appears in judgment search', async ({ browser }) => {
  const lead = await signedIn(browser, 'advocate');
  const caseId = await sattvikId(lead);
  const upload = await lead.request.post(`/api/cases/${caseId}/documents`, {
    headers: CHANGE_HEADERS,
    multipart: {
      file: {
        name: 'e2e-private-memo.txt',
        mimeType: 'text/plain',
        buffer: Buffer.from('FICTIONAL CONFIDENTIAL memo: quixotically zymurgy strategy.'),
      },
    },
  });
  expect(upload.status()).toBe(201);
  const document = (await upload.json()) as { id: string };
  // Wait until the worker has extracted it (so it is searchable inside the case).
  await expect
    .poll(
      async () =>
        (await (await lead.request.get(`/api/cases/${caseId}/search?q=zymurgy`)).json()).results
          .length,
      { timeout: 60_000 },
    )
    .toBe(1);
  const judgments = await (await lead.request.get('/api/judgments/search?q=zymurgy')).json();
  expect(judgments.total).toBe(0);
  expect(
    (
      await lead.request.delete(`/api/documents/${document.id}`, { headers: CHANGE_HEADERS })
    ).status(),
  ).toBe(204);
  await lead.context().close();
});
