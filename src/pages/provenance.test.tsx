import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../test/renderApp';
import { ARYAN_EMAIL } from '../test/mockApi';
import { mockSetJudgments, syntheticJudgment } from '../test/mockJudgments';

// Genuine and synthetic judgments side by side (Batch 2). Every record here is
// INVENTED; the "unflagged" one only stands in for a judgment from a real
// source, so the labels, the origin filter and the provenance panel can be
// checked. The filter itself is tested on the server (test_judgments_api.py).

const LIBRARY = '/app/precedents';

const invented = syntheticJudgment(1, 'Asha Rao v. Bharat Traders (SYNTHETIC)', [
  'FICTIONAL. The tenant stopped paying rent.',
]);
const base = syntheticJudgment(2, 'TEST ONLY Unflagged v. Record (not real law)', [
  'TEST ONLY. Passing off and prior use of a mark.',
]);
const unflagged = {
  ...base,
  detail: {
    ...base.detail,
    synthetic: false,
    sourceName: 'TEST ONLY unflagged source',
    source: { ...base.detail.source, name: 'TEST ONLY unflagged source', synthetic: false },
    provenance: {
      neutralCitation: 'TEST-NC-0002',
      attribution: 'TEST ONLY attribution: shown with every judgment from this source.',
      dataset: {
        name: 'TEST ONLY dataset',
        publisher: 'LexFlow tests',
        url: 'https://fixtures.lexflow.invalid/test',
        version: null,
        retrievedOn: '2026-10-25',
      },
      sourceRecord: {
        file_sha256: 'ab'.repeat(32),
        selected_by: 'TEST ONLY technical selection, not a legal review',
        legal_review: 'not performed',
        corpus_role: 'evaluation candidate',
        notes: 'TEST ONLY editorial headnote on page 1',
        original_sha256: 'cd'.repeat(32),
        original_transform: 'TEST ONLY prefix removed',
      },
      recordedAt: '2026-10-25T09:00:00Z',
    },
  },
};

describe('Genuine and synthetic judgments', () => {
  it('labels each kind and filters the library by origin', async () => {
    mockSetJudgments([invented, unflagged]);
    const { user, url } = renderApp(LIBRARY, { as: ARYAN_EMAIL });
    const genuine = await screen.findByRole('article', { name: unflagged.detail.title });
    expect(within(genuine).getByText('Genuine judgment')).toBeVisible();
    const fake = screen.getByRole('article', { name: invented.detail.title });
    expect(within(fake).getByText('Synthetic test data')).toBeVisible();

    await user.selectOptions(screen.getByLabelText('Origin'), 'genuine');
    await user.click(screen.getByRole('button', { name: 'Apply filters' }));
    expect(await screen.findByText('1 judgment, newest first.')).toBeVisible();
    expect(url()).toContain('origin=genuine');
    expect(screen.queryByRole('article', { name: invented.detail.title })).toBeNull();
  });

  it('offers no origin filter when the whole collection is synthetic', async () => {
    mockSetJudgments([invented]);
    renderApp(LIBRARY, { as: ARYAN_EMAIL });
    expect(await screen.findByText('1 judgment, newest first.')).toBeVisible();
    expect(screen.queryByLabelText('Origin')).toBeNull();
  });

  it('shows the provenance and the reliance caution of a genuine judgment', async () => {
    mockSetJudgments([unflagged]);
    renderApp(`${LIBRARY}/${unflagged.detail.id}`, { as: ARYAN_EMAIL });
    expect(await screen.findByRole('heading', { name: /TEST ONLY Unflagged/ })).toBeVisible();
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.getByText(/not by judging\s+its legal relevance/)).toBeVisible();
    expect(screen.getByText(/TEST ONLY attribution/)).toBeVisible();
    expect(screen.getByText('TEST-NC-0002')).toBeVisible();
    expect(screen.getByText(/TEST ONLY dataset \(LexFlow tests\)/)).toBeVisible();
    expect(screen.getByText('ab'.repeat(32))).toBeVisible();
    expect(screen.getByText('TEST ONLY technical selection, not a legal review')).toBeVisible();
    expect(screen.getByText('not performed')).toBeVisible();
    expect(screen.getByText('evaluation candidate')).toBeVisible();
    expect(screen.getByText('TEST ONLY editorial headnote on page 1')).toBeVisible();
    expect(screen.getByText(/TEST ONLY prefix removed/)).toBeVisible();
    expect(screen.getByText('cd'.repeat(32))).toBeVisible();
  });
});
