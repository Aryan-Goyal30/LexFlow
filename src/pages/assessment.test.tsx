import { act, cleanup, screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../test/renderApp';
import {
  ARYAN_EMAIL,
  MOCK_PARALEGAL_EMAIL,
  mockAddMember,
  mockApiState,
  mockReadyText,
  problem,
  server,
} from '../test/mockApi';
import {
  mockAnalysisAvailable,
  mockAnalysisRuns,
  mockAssessmentsEnabled,
  mockFinishRun,
  mockNextAssessment,
} from '../test/mockAnalysis';
import type { AnalysisResult, AssessmentResult } from '../types/ai';

// The outcome assessment (Phase 7, synthetic engineering demo) against the fake
// routes (SYNTHETIC data). The server's rules are tested in
// server/tests/test_assessments_api.py and test_assessment_validation.py; here:
// what the advocate sees, that nothing appears while the flag is off, and that
// no assessment is shown as a lawyer's view before a reviewer accepts it.

const CASE_ID = 'case-1005';
const TAB = `/app/cases/${CASE_ID}?tab=analysis`;
const SUMMARY = '[Scripted] Demonstration assessment built from accepted findings.';
const QUOTE = 'SYNTHETIC: prior use is weighed against adoption.';

function readyDocuments() {
  const c = mockApiState().cases.find((x) => x.id === CASE_ID);
  if (!c) throw new Error('no sample case');
  const [first] = c.documents;
  mockReadyText(first.id, ['SYNTHETIC page one.', 'SYNTHETIC page two.']);
  return first;
}

function analysis(documentId: string, documentName: string): AnalysisResult {
  const source = {
    evidenceId: 'D2',
    documentId,
    documentName,
    chunkId: 'chunk-2',
    sectionNumber: 2,
    pageNumber: 2,
    quote: 'SYNTHETIC page two.',
  };
  return {
    facts: [{ id: 'F1', statement: 'SYNTHETIC: the mark was registered in 2015.', source }],
    issues: [],
    precedents: [
      {
        id: 'P1',
        evidenceId: 'J1',
        judgmentId: 'judgment-1',
        title: 'Asha Rao v. Bharat Traders (SYNTHETIC)',
        court: 'SYNTHETIC District Court (test fixture)',
        citation: '(SYN) 2019 TEST 101',
        year: 2019,
        synthetic: true,
        retrievalRank: 1,
        passage: { chunkId: 'jchunk-1', sectionNumber: 3, pageNumber: 3 },
        summary: 'SYNTHETIC: prior use is weighed against adoption.',
        similarities: [],
        differences: [],
      },
    ],
    contradictions: [],
    insufficientEvidence: false,
    insufficientReason: null,
    precedentsAvailable: true,
    removed: { count: 0, reasons: [] },
  };
}

const READY: AssessmentResult = {
  label: 'decision-support',
  summary: SUMMARY,
  uncertainty: 'mixed_evidence',
  precedents: [
    {
      ref: 'P1',
      judgmentId: 'judgment-1',
      title: 'Asha Rao v. Bharat Traders (SYNTHETIC)',
      court: 'SYNTHETIC District Court (test fixture)',
      citation: '(SYN) 2019 TEST 101',
      year: 2019,
      synthetic: true,
      passage: { chunkId: 'jchunk-1', sectionNumber: 3, pageNumber: 3 },
      stance: 'supports',
      quote: QUOTE,
      explanation: '[Scripted] P1 is read as supporting the position.',
    },
  ],
  reasoning: [
    {
      id: 'R1',
      text: '[Scripted] F1 is read together with P1.',
      findingIds: ['F1'],
      precedentRefs: ['P1'],
    },
  ],
  missingEvidence: ['[Scripted] Judgments from an approved source.'],
  limitations: ['[Scripted] Stances were assigned by position.'],
  allPrecedentsSynthetic: true,
  demoOnly: true,
  removed: {
    count: 1,
    reasons: [
      {
        code: 'unknown-precedent',
        message: 'Cited a precedent that is not an accepted comparison of this analysis.',
        count: 1,
      },
    ],
  },
};

async function openFinished({ enabled = true, as = ARYAN_EMAIL } = {}) {
  mockAnalysisAvailable({ provider: 'scripted', model: 'scripted-v1' });
  if (enabled) mockAssessmentsEnabled();
  const doc = readyDocuments();
  const app = renderApp(TAB, { as: ARYAN_EMAIL });
  await app.user.click(await screen.findByRole('checkbox', { name: /I confirm/ }));
  await app.user.click(screen.getByRole('button', { name: /Analyse case/ }));
  await screen.findByText(/Waiting for the worker/);
  const [run] = mockAnalysisRuns();
  mockFinishRun(run.id, { result: analysis(doc.id, doc.name) });
  if (as === ARYAN_EMAIL) {
    await act(() => app.queryClient.invalidateQueries());
    await screen.findByText(/Lawyer review: 0 of 2 findings reviewed/);
    return { ...app, run };
  }
  cleanup();
  const other = renderApp(TAB, { as });
  await screen.findByText(/Lawyer review: 0 of 2 findings reviewed/);
  return { ...other, run };
}

const card = () => screen.getByRole('region', { name: /Outcome assessment \(decision support\)/ });
const reviewOf = (label: string) => screen.getByRole('region', { name: `Review of ${label}` });

async function acceptBoth(user: ReturnType<typeof renderApp>['user']) {
  for (const label of ['Fact F1', 'Precedent comparison P1']) {
    await user.click(within(reviewOf(label)).getByRole('button', { name: 'Accept' }));
    await within(reviewOf(label)).findByText('Accepted');
  }
}

describe('The outcome assessment (Phase 7 demo)', () => {
  it('shows nothing and asks nothing while the flag is off', async () => {
    let asked = false;
    server.use(
      http.get('*/api/cases/:id/analysis-runs/:runId/assessments', () => {
        asked = true;
        return HttpResponse.json({});
      }),
    );
    await openFinished({ enabled: false });
    expect(screen.queryByText(/Outcome assessment/)).toBeNull();
    expect(screen.queryByRole('button', { name: /Generate assessment/ })).toBeNull();
    expect(asked).toBe(false);
  });

  it('cannot be generated before a lawyer accepts findings and a precedent', async () => {
    await openFinished();
    const panel = await screen.findByRole('region', {
      name: /Outcome assessment \(decision support\)/,
    });
    expect(within(panel).getByText(/Decision support, not a prediction/)).toBeVisible();
    expect(
      await within(panel).findByRole('button', { name: /Generate assessment/ }),
    ).toBeDisabled();
    expect(within(panel).getByText(/has been accepted by a lawyer yet/)).toBeVisible();
    expect(
      within(panel).getByText(/Uses 0 accepted findings and 0 accepted precedent/),
    ).toBeVisible();
  });

  it('shows a verified, labelled, synthetic assessment as unreviewed', async () => {
    const { user } = await openFinished();
    await acceptBoth(user);
    mockNextAssessment({ status: 'ready', result: READY });
    await user.click(await within(card()).findByRole('button', { name: /Generate assessment/ }));
    const view = await within(card()).findByRole('region', { name: /Assessment of/ });
    expect(
      within(view).getByRole('note', { name: 'Demonstration on synthetic data' }),
    ).toBeVisible();
    expect(within(view).getByText('Mixed evidence')).toBeVisible();
    expect(within(view).getByText('(a category, not a probability)')).toBeVisible();
    expect(within(view).getByText(SUMMARY)).toBeVisible();
    expect(within(view).getByText('Supports')).toBeVisible();
    expect(within(view).getByText('Synthetic test data')).toBeVisible();
    expect(within(view).getByText(`“${QUOTE}”`)).toBeVisible();
    expect(within(view).getByRole('link', { name: /Read the passage \(page 3\)/ })).toHaveAttribute(
      'href',
      '/app/precedents/judgment-1?section=3',
    );
    expect(within(view).getByText(/rests on F1, P1/)).toBeVisible();
    expect(within(view).getByText(/1 item was removed by the server/)).toBeVisible();
    const lawyer = within(view).getByRole('region', { name: 'Lawyer review of this assessment' });
    expect(within(lawyer).getByText('Unreviewed')).toBeVisible();
    expect(within(lawyer).getByText(/Not yet reviewed: this is not a lawyer/)).toBeVisible();
    expect(card().textContent).not.toMatch(/\d\s*%|probability of|chance of winning/i);
  });

  it('says plainly when there is no basis, and when generation failed', async () => {
    const { user } = await openFinished();
    await user.click(within(reviewOf('Fact F1')).getByRole('button', { name: 'Accept' }));
    await within(reviewOf('Fact F1')).findByText('Accepted');
    // Generation is refused by the server's gate (no accepted precedent): the
    // button says so; a lawyer cannot even ask.
    expect(
      await within(card()).findByRole('button', { name: /Generate assessment/ }),
    ).toBeDisabled();

    await user.click(
      within(reviewOf('Precedent comparison P1')).getByRole('button', { name: 'Accept' }),
    );
    await within(reviewOf('Precedent comparison P1')).findByText('Accepted');
    mockNextAssessment({
      status: 'failed',
      reasonCode: 'provider-timeout',
      reason: 'The provider did not answer in time.',
    });
    await user.click(await within(card()).findByRole('button', { name: /Generate assessment/ }));
    expect(
      await within(card()).findByText(/The assessment failed: The provider did not/),
    ).toBeVisible();

    mockNextAssessment({
      status: 'insufficient',
      reasonCode: 'summary-withheld',
      reason: 'The assessment stated a probability, so nothing from it is shown.',
    });
    await user.click(within(card()).getByRole('button', { name: /Generate assessment/ }));
    expect(await within(card()).findByText(/No assessment: insufficient basis/)).toBeVisible();
    expect(within(card()).getByText('Earlier assessments')).toBeVisible();
  });

  it('reports a request that failed without showing anything', async () => {
    const { user } = await openFinished();
    await acceptBoth(user);
    server.use(
      http.post('*/api/cases/:id/analysis-runs/:runId/assessments', () =>
        problem(503, 'assessment-model-not-approved', 'A real AI model is not enabled.'),
      ),
    );
    await user.click(await within(card()).findByRole('button', { name: /Generate assessment/ }));
    expect(await within(card()).findByRole('alert')).toHaveTextContent(
      /No assessment was generated. A real AI model is not enabled./,
    );
    expect(within(card()).queryByRole('region', { name: /Assessment of/ })).toBeNull();
  });

  it('records the lawyer’s decisions only after the server stores them', async () => {
    const { user } = await openFinished();
    await acceptBoth(user);
    mockNextAssessment({ status: 'ready', result: READY });
    await user.click(await within(card()).findByRole('button', { name: /Generate assessment/ }));
    const lawyer = await within(card()).findByRole('region', {
      name: 'Lawyer review of this assessment',
    });
    await user.click(within(lawyer).getByRole('button', { name: 'Accept assessment' }));
    expect(await within(lawyer).findByText('Accepted')).toBeVisible();
    expect(within(lawyer).getByText(/by Aryan Goyal/)).toBeVisible();
    expect(within(lawyer).getByText(/The case brief includes it in its own section/)).toBeVisible();

    await user.click(within(lawyer).getByRole('button', { name: 'Edit summary' }));
    const box = within(lawyer).getByLabelText('Lawyer’s wording of the summary');
    expect(box).toHaveValue(SUMMARY);
    await user.clear(box);
    await user.type(box, 'SYNTHETIC lawyer wording.');
    await user.type(within(lawyer).getByLabelText(/Note \(optional/), 'SYNTHETIC note');
    await user.click(within(lawyer).getByRole('button', { name: 'Save wording' }));
    expect(await within(lawyer).findByText('Edited by lawyer')).toBeVisible();
    expect(within(lawyer).getByText('SYNTHETIC lawyer wording.')).toBeVisible();
    expect(within(card()).getByText(SUMMARY)).toBeVisible(); // the original stays
    expect(within(lawyer).getByText('SYNTHETIC note')).toBeVisible();

    await user.click(within(lawyer).getByRole('button', { name: 'Show history' }));
    const history = await within(lawyer).findByRole('list', {
      name: 'History of the assessment review',
    });
    expect(within(history).getAllByRole('listitem')).toHaveLength(2);
  });

  it('shows a stale decision and reloads the current one', async () => {
    const { user } = await openFinished();
    await acceptBoth(user);
    mockNextAssessment({ status: 'ready', result: READY });
    await user.click(await within(card()).findByRole('button', { name: /Generate assessment/ }));
    const lawyer = await within(card()).findByRole('region', {
      name: 'Lawyer review of this assessment',
    });
    server.use(
      http.put('*/api/cases/:id/analysis-runs/:runId/assessments/:assessmentId/review', () =>
        problem(409, 'review-changed', 'This assessment was reviewed again in the meantime.'),
      ),
    );
    await user.click(within(lawyer).getByRole('button', { name: 'Accept assessment' }));
    expect(await within(lawyer).findByRole('alert')).toHaveTextContent(/reviewed again/);
    expect(within(lawyer).getByText('Unreviewed')).toBeVisible();
  });

  it('lets a paralegal read the assessment but not generate, decide or see notes', async () => {
    mockAddMember(CASE_ID, MOCK_PARALEGAL_EMAIL, 'paralegal');
    const { user, run } = await openFinished();
    await acceptBoth(user);
    mockNextAssessment({ status: 'ready', result: READY });
    await user.click(await within(card()).findByRole('button', { name: /Generate assessment/ }));
    const lawyer = await within(card()).findByRole('region', {
      name: 'Lawyer review of this assessment',
    });
    await user.click(within(lawyer).getByRole('button', { name: 'Reject' }));
    await user.type(within(lawyer).getByLabelText(/Reason for rejecting/), 'SYNTHETIC reason');
    await user.click(within(lawyer).getByRole('button', { name: 'Reject assessment' }));
    await within(lawyer).findByText('Rejected');
    void run;

    cleanup();
    renderApp(TAB, { as: MOCK_PARALEGAL_EMAIL });
    const panel = await screen.findByRole('region', {
      name: /Outcome assessment \(decision support\)/,
    });
    expect(await within(panel).findByText('Rejected')).toBeVisible();
    expect(within(panel).getByRole('button', { name: /Generate assessment/ })).toBeDisabled();
    expect(within(panel).getByText(/Only the case's advocates and administrators/)).toBeVisible();
    expect(
      within(panel).queryByRole('button', { name: /Accept assessment|Edit summary/ }),
    ).toBeNull();
    expect(within(panel).queryByText('SYNTHETIC reason')).toBeNull();
  });
});
