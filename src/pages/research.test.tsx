import { screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../test/renderApp';
import { ARYAN_EMAIL } from '../test/mockApi';
import { mockJudgmentOptions, mockSetJudgments, syntheticJudgment } from '../test/mockJudgments';

// Research tab and Precedent Library against the fake judgment collection
// (SYNTHETIC records). Ranking, access control and validation are tested on
// the server (server/tests/test_judgments_api.py).

const CASE = '/app/cases/case-1005?tab=research';
const LIBRARY = '/app/precedents';

const tenancy = syntheticJudgment(1, 'Asha Rao v. Bharat Traders (SYNTHETIC)', [
  'FICTIONAL. The tenant stopped paying rent and the arrears grew.',
  'FICTIONAL. The court decreed the arrears with interest.',
]);
const notice = syntheticJudgment(2, 'Kiran Mehta v. Sunil Gowda (SYNTHETIC)', [
  'FICTIONAL. A notice to quit must give fifteen clear days.',
]);
const trademark = syntheticJudgment(
  3,
  'Golden Grain Foods v. Sunrise Bakers (SYNTHETIC)',
  ['FICTIONAL. The marks were deceptively similar.'],
  { court: 'SYNTHETIC District Court (test fixture)', citation: null },
);

async function searchFor(user: ReturnType<typeof renderApp>['user'], text: string) {
  const box = await screen.findByRole('searchbox', { name: /Search/ });
  await user.clear(box);
  if (text) await user.type(box, text);
  await user.click(screen.getByRole('button', { name: 'Search' }));
}

describe('Research tab', () => {
  it('says so when the collection is empty', async () => {
    renderApp(CASE, { as: ARYAN_EMAIL });
    expect(await screen.findByText('The judgment collection is empty')).toBeVisible();
  });

  it('finds judgments and shows each with its passage, source and synthetic label', async () => {
    mockSetJudgments([tenancy, notice, trademark]);
    const { user } = renderApp(CASE, { as: ARYAN_EMAIL });
    await searchFor(user, 'arrears');

    expect(await screen.findByText('1 judgment matched “arrears” · Keywords')).toBeVisible();
    const card = screen.getByRole('article', { name: tenancy.detail.title });
    expect(within(card).getByText(/tenant stopped paying rent/)).toBeVisible();
    expect(within(card).getByText('Page 1')).toBeVisible();
    expect(within(card).getByText('Synthetic test data')).toBeVisible();
    expect(
      within(card).getByText(/SYNTHETIC High Court \(test fixture\) · .* · \(SYN\)/),
    ).toBeVisible();
    const read = within(card).getByRole('link', { name: `Read ${tenancy.detail.title}` });
    expect(read).toHaveAttribute('href', `/app/precedents/${tenancy.detail.id}`);
    const source = within(card).getByRole('link', { name: /View at source/ });
    expect(source).toHaveAttribute('href', 'https://judgments.lexflow.invalid/syn-1');
    expect(source).toHaveAttribute('target', '_blank');
    expect(source).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('reports no matches, and refuses an empty search', async () => {
    mockSetJudgments([tenancy]);
    const { user } = renderApp(CASE, { as: ARYAN_EMAIL });
    await searchFor(user, 'spaceship');
    expect(await screen.findByText('No judgments matched “spaceship”.')).toBeVisible();
    await searchFor(user, '   ');
    expect(screen.getByRole('alert')).toHaveTextContent('Type something to search for.');
  });

  it('offers meaning-based search only when the server can do it', async () => {
    mockSetJudgments([tenancy]);
    renderApp(CASE, { as: ARYAN_EMAIL });
    const option = await screen.findByRole('option', { name: /Meaning \(semantic\)/ });
    expect(option).toBeDisabled();
    expect(
      screen.getByText(/Searching by meaning is unavailable: Semantic search is off/),
    ).toBeVisible();
  });

  it('uses semantic search when available', async () => {
    mockSetJudgments([tenancy]);
    mockJudgmentOptions({ semantic: { available: true, reason: null } });
    const { user } = renderApp(CASE, { as: ARYAN_EMAIL });
    await user.selectOptions(
      await screen.findByRole('combobox', { name: 'Search by' }),
      'semantic',
    );
    await searchFor(user, 'rent');
    expect(await screen.findByText(/matched “rent” · Meaning \(semantic\)/)).toBeVisible();
  });

  it('shows a recoverable error when the search fails', async () => {
    mockSetJudgments([tenancy]);
    mockJudgmentOptions({ failSearch: true });
    const { user } = renderApp(CASE, { as: ARYAN_EMAIL });
    await searchFor(user, 'rent');
    expect(await screen.findByText('The search did not work')).toBeVisible();
    mockJudgmentOptions({ failSearch: false });
    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText(/1 judgment matched “rent”/)).toBeVisible();
  });

  it('never shows the results of an earlier search as those of a new one', async () => {
    mockSetJudgments([tenancy, notice]);
    mockJudgmentOptions({ slowQuery: 'fifteen' });
    const { user } = renderApp(CASE, { as: ARYAN_EMAIL });
    await searchFor(user, 'arrears');
    expect(await screen.findByText(/matched “arrears”/)).toBeVisible();
    await searchFor(user, 'fifteen');
    // While the new search runs, the old results are gone.
    expect(screen.getByText('Searching for “fifteen”…')).toBeVisible();
    expect(screen.queryByRole('article', { name: tenancy.detail.title })).toBeNull();
    expect(await screen.findByRole('article', { name: notice.detail.title })).toBeVisible();
    expect(screen.queryByRole('article', { name: tenancy.detail.title })).toBeNull();
  });

  it('pages through many results', async () => {
    mockSetJudgments(
      Array.from({ length: 12 }, (_, i) =>
        syntheticJudgment(i + 10, `Case ${String(i + 1).padStart(2, '0')} (SYNTHETIC)`, [
          'FICTIONAL. Common words about rent.',
        ]),
      ),
    );
    const { user } = renderApp(CASE, { as: ARYAN_EMAIL });
    await searchFor(user, 'rent');
    expect(await screen.findByText('Page 1 of 2')).toBeVisible();
    expect(screen.getAllByRole('article')).toHaveLength(10);
    await user.click(screen.getByRole('button', { name: /Next/ }));
    expect(await screen.findByText('Page 2 of 2')).toBeVisible();
    expect(screen.getAllByRole('article')).toHaveLength(2);
  });

  it('never links to a source address that is not https', async () => {
    mockSetJudgments([
      syntheticJudgment(4, 'Unsafe link (SYNTHETIC)', ['FICTIONAL. rent'], {
        sourceUrl: 'javascript:alert(1)',
      }),
    ]);
    const { user } = renderApp(CASE, { as: ARYAN_EMAIL });
    await searchFor(user, 'rent');
    const card = await screen.findByRole('article', { name: 'Unsafe link (SYNTHETIC)' });
    expect(within(card).queryByRole('link', { name: /View at source/ })).toBeNull();
  });
});

describe('Precedent Library', () => {
  it('is in the sidebar and lists the collection newest first', async () => {
    mockSetJudgments([tenancy, notice, trademark]);
    const { user, url } = renderApp('/app/cases', { as: ARYAN_EMAIL });
    await user.click(await screen.findByRole('link', { name: 'Precedent Library' }));
    expect(url()).toBe(LIBRARY);
    expect(await screen.findByText('3 judgments, newest first.')).toBeVisible();
    expect(screen.getByRole('note')).toHaveTextContent(
      'Every judgment here is synthetic test data: invented, not real judgments, never to be cited.',
    );
    const titles = screen.getAllByRole('article').map((a) => a.getAttribute('aria-label'));
    expect(titles).toEqual([trademark.detail.title, notice.detail.title, tenancy.detail.title]);
  });

  it('filters by court and searches through the address', async () => {
    mockSetJudgments([tenancy, notice, trademark]);
    const { user, url } = renderApp(LIBRARY, { as: ARYAN_EMAIL });
    await user.selectOptions(
      await screen.findByLabelText('Court'),
      'SYNTHETIC District Court (test fixture)',
    );
    await user.click(screen.getByRole('button', { name: 'Apply filters' }));
    expect(await screen.findByText('1 judgment, newest first.')).toBeVisible();
    expect(url()).toContain('court=SYNTHETIC+District+Court');
    await searchFor(user, 'deceptively');
    await waitFor(() => expect(url()).toContain('q=deceptively'));
    expect(await screen.findByText(/1 judgment matched “deceptively”/)).toBeVisible();
  });

  it('opens a search straight from its address', async () => {
    mockSetJudgments([tenancy, notice]);
    renderApp(`${LIBRARY}?q=notice&mode=keyword`, { as: ARYAN_EMAIL });
    expect(await screen.findByRole('article', { name: notice.detail.title })).toBeVisible();
    expect(screen.getByRole('searchbox')).toHaveValue('notice');
  });

  it('says so when the collection is empty', async () => {
    renderApp(LIBRARY, { as: ARYAN_EMAIL });
    expect(await screen.findByText('The judgment collection is empty')).toBeVisible();
  });
});

describe('A judgment', () => {
  it('shows its source, terms of use, synthetic warning and text page by page', async () => {
    mockSetJudgments([tenancy]);
    const { user, url } = renderApp(`${LIBRARY}/${tenancy.detail.id}`, { as: ARYAN_EMAIL });
    expect(
      await screen.findByRole('heading', { name: /Asha Rao v\. Bharat Traders/ }),
    ).toBeVisible();
    expect(screen.getByRole('alert')).toHaveTextContent('Synthetic test data');
    expect(screen.getByText('LexFlow synthetic test judgments')).toBeVisible();
    expect(screen.getByText(/Invented for automated tests only/)).toBeVisible();
    expect(screen.getByRole('link', { name: 'the terms' })).toHaveAttribute(
      'href',
      'https://terms.lexflow.invalid/synthetic',
    );
    expect(await screen.findByRole('article', { name: 'Page 1 of 2' })).toHaveTextContent(
      'tenant stopped paying rent',
    );
    await user.click(screen.getByRole('link', { name: /Next page/ }));
    expect(await screen.findByRole('article', { name: 'Page 2 of 2' })).toHaveTextContent(
      'decreed the arrears',
    );
    expect(url()).toBe(`${LIBRARY}/${tenancy.detail.id}?section=2`);
  });

  it('says when a judgment does not exist', async () => {
    renderApp(`${LIBRARY}/00000000-0000-4000-8000-999999999999`, { as: ARYAN_EMAIL });
    expect(await screen.findByText('Not found')).toBeVisible();
  });
});

describe('Keyword search with no passage containing every word', () => {
  it('shows passages with some of the words and says so', async () => {
    mockSetJudgments([tenancy, notice]);
    renderApp(`${LIBRARY}?q=${encodeURIComponent('notice zebra')}&mode=keyword`, {
      as: ARYAN_EMAIL,
    });
    expect(await screen.findByRole('article', { name: notice.detail.title })).toBeVisible();
    expect(screen.getByText(/No passage contains every word of your search/)).toBeVisible();
  });

  it('adds no note when every word matched', async () => {
    mockSetJudgments([tenancy, notice]);
    renderApp(`${LIBRARY}?q=notice&mode=keyword`, { as: ARYAN_EMAIL });
    expect(await screen.findByRole('article', { name: notice.detail.title })).toBeVisible();
    expect(screen.queryByText(/No passage contains every word/)).toBeNull();
  });
});
