import { act, cleanup, screen, waitFor, within } from '@testing-library/react';
import { http } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
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
  mockFinishRun,
  mockReviewElsewhere,
  mockReviewsUnavailable,
} from '../test/mockAnalysis';
import type { AnalysisResult } from '../types/ai';

// Lawyer review of AI findings (Phase 6) against the fake review routes
// (SYNTHETIC data). The server's rules are tested in
// server/tests/test_analysis_reviews.py; here: what the lawyer sees and sends.

const CASE_ID = 'case-1005';
const TAB = `/app/cases/${CASE_ID}?tab=analysis`;
const AI_FACT = 'SYNTHETIC: the rent was agreed in writing.';

function readyDocuments() {
  const c = mockApiState().cases.find((x) => x.id === CASE_ID);
  if (!c) throw new Error('no sample case');
  const [first, second] = c.documents;
  mockReadyText(first.id, ['SYNTHETIC page one.', 'SYNTHETIC page two.']);
  mockReadyText(second.id, ['SYNTHETIC reply.']);
  return [first, second];
}

function result(documentId: string, documentName: string): AnalysisResult {
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
    facts: [{ id: 'F1', statement: AI_FACT, source }],
    issues: [{ id: 'I1', question: 'Which rent applies?', factIds: ['F1'] }],
    precedents: [],
    contradictions: [
      {
        id: 'C1',
        description: 'SYNTHETIC: the notice and the agreement give different rents.',
        sources: [source, { ...source, evidenceId: 'D1', sectionNumber: 1, pageNumber: 1 }],
      },
    ],
    insufficientEvidence: false,
    insufficientReason: null,
    precedentsAvailable: false,
    removed: { count: 0, reasons: [] },
  };
}

async function openFinished(changed: string[] = [], as = ARYAN_EMAIL) {
  mockAnalysisAvailable();
  const [first] = readyDocuments();
  const app = renderApp(TAB, { as: ARYAN_EMAIL });
  await app.user.click(await screen.findByRole('checkbox', { name: /I confirm/ }));
  await app.user.click(screen.getByRole('button', { name: /Analyse case/ }));
  await screen.findByText(/Waiting for the worker/);
  const [run] = mockAnalysisRuns();
  mockFinishRun(run.id, { result: result(first.id, first.name), changed });
  if (as === ARYAN_EMAIL) {
    await act(() => app.queryClient.invalidateQueries());
    await screen.findByText(/Lawyer review: 0 of 3 findings reviewed/);
    return { ...app, run };
  }
  cleanup(); // unmount the lead's view, then open the run as someone else
  const other = renderApp(TAB, { as });
  await screen.findByText(/Lawyer review: 0 of 3 findings reviewed/);
  return { ...other, run };
}

const panel = (label: string) => screen.getByRole('region', { name: `Review of ${label}` });

describe('Reviewing AI findings', () => {
  it('marks every finding as unreviewed until a lawyer decides', async () => {
    await openFinished();
    for (const label of ['Fact F1', 'Issue I1', 'Contradiction C1']) {
      expect(within(panel(label)).getByText('Unreviewed')).toBeVisible();
    }
    expect(screen.getByText(/Unreviewed findings are the AI’s, not yet checked/)).toBeVisible();
  });

  it('records an acceptance only after the server has stored it', async () => {
    const { user } = await openFinished();
    await user.click(within(panel('Fact F1')).getByRole('button', { name: 'Accept' }));
    expect(await within(panel('Fact F1')).findByText('Accepted')).toBeVisible();
    expect(within(panel('Fact F1')).getByText(/Accepted by Aryan Goyal/)).toBeVisible();
    expect(screen.getByText(/Lawyer review: 1 of 3 findings reviewed/)).toBeVisible();
  });

  it('keeps a finding unreviewed and says why when saving fails', async () => {
    const { user } = await openFinished();
    server.use(
      http.put('*/api/cases/:id/analysis-runs/:runId/reviews/:findingId', () =>
        problem(500, 'server-error', 'Something went wrong on the server.'),
      ),
    );
    await user.click(within(panel('Fact F1')).getByRole('button', { name: 'Accept' }));
    expect(await within(panel('Fact F1')).findByRole('alert')).toBeVisible();
    expect(within(panel('Fact F1')).getByText('Unreviewed')).toBeVisible();
    expect(within(panel('Fact F1')).queryByText('Accepted')).not.toBeInTheDocument();
  });

  it('edits the wording, keeping the AI’s original on screen', async () => {
    const { user } = await openFinished();
    await user.click(within(panel('Fact F1')).getByRole('button', { name: 'Edit wording' }));
    const wording = within(panel('Fact F1')).getByLabelText(/Lawyer’s wording for Fact F1/);
    expect(wording).toHaveValue(AI_FACT);
    await user.clear(wording);
    await user.type(wording, 'SYNTHETIC: the rent of Rs. 40,000 was agreed in writing.');
    await user.type(
      within(panel('Fact F1')).getByLabelText(/Note \(optional/),
      'SYNTHETIC: checked clause 3',
    );
    await user.click(within(panel('Fact F1')).getByRole('button', { name: 'Save wording' }));
    const done = panel('Fact F1');
    expect(await within(done).findByText('Edited by lawyer')).toBeVisible();
    expect(within(done).getByText(/the rent of Rs. 40,000 was agreed in writing/)).toBeVisible();
    expect(within(done).getByText(/SYNTHETIC: checked clause 3/)).toBeVisible();
    expect(screen.getByText(AI_FACT)).toBeVisible(); // the model's wording stays the record
  });

  it('rejects with a reason, clears after confirmation, and shows the history', async () => {
    const { user } = await openFinished();
    const contradiction = () => panel('Contradiction C1');
    await user.click(within(contradiction()).getByRole('button', { name: 'Reject' }));
    await user.type(
      within(contradiction()).getByLabelText(/Reason for rejecting/),
      'SYNTHETIC: the amounts are for different months',
    );
    await user.click(within(contradiction()).getByRole('button', { name: 'Reject finding' }));
    expect(await within(contradiction()).findByText('Rejected')).toBeVisible();
    expect(within(contradiction()).getByText(/different months/)).toBeVisible();

    await user.click(within(contradiction()).getByRole('button', { name: 'Clear decision' }));
    expect(
      within(contradiction()).getByText(/Return Contradiction C1 to unreviewed\?/),
    ).toBeVisible();
    await user.click(within(contradiction()).getByRole('button', { name: 'Clear decision' }));
    expect(await within(contradiction()).findByText('Unreviewed')).toBeVisible();

    await user.click(within(contradiction()).getByRole('button', { name: 'Show history' }));
    const history = await within(contradiction()).findByRole('list', { name: 'History of C1' });
    const entries = within(history).getAllByRole('listitem');
    expect(entries).toHaveLength(2);
    expect(entries[0]).toHaveTextContent(/Rejected by Aryan Goyal/);
    expect(entries[1]).toHaveTextContent(/Returned to unreviewed by Aryan Goyal/);
  });

  it('shows the current decision when someone else reviewed meanwhile', async () => {
    const { user, run } = await openFinished();
    mockReviewElsewhere(run.id, 'F1', 'rejected');
    await user.click(within(panel('Fact F1')).getByRole('button', { name: 'Accept' }));
    expect(await within(panel('Fact F1')).findByRole('alert')).toHaveTextContent(
      /reviewed again in the meantime/,
    );
    await waitFor(() => expect(within(panel('Fact F1')).getByText('Rejected')).toBeVisible());
    expect(within(panel('Fact F1')).getByText(/by Another Reviewer/)).toBeVisible();
  });

  it('warns when a finding’s source changed after the analysis', async () => {
    await openFinished(['D2']);
    expect(
      within(panel('Fact F1')).getByText(/A source of this finding changed after the analysis/),
    ).toBeVisible();
    expect(
      within(panel('Issue I1')).queryByText(/A source of this finding changed/),
    ).not.toBeInTheDocument();
  });

  it('gives a paralegal the decisions but no controls', async () => {
    mockAddMember(CASE_ID, MOCK_PARALEGAL_EMAIL, 'paralegal');
    await openFinished([], MOCK_PARALEGAL_EMAIL);
    const fact = panel('Fact F1');
    expect(within(fact).getByText('Unreviewed')).toBeVisible();
    for (const name of ['Accept', 'Edit wording', 'Reject']) {
      expect(within(fact).queryByRole('button', { name })).not.toBeInTheDocument();
    }
  });

  it('says plainly when review is unavailable, with a retry', async () => {
    mockReviewsUnavailable();
    mockAnalysisAvailable();
    const [first] = readyDocuments();
    const app = renderApp(TAB, { as: ARYAN_EMAIL });
    await app.user.click(await screen.findByRole('checkbox', { name: /I confirm/ }));
    await app.user.click(screen.getByRole('button', { name: /Analyse case/ }));
    await screen.findByText(/Waiting for the worker/);
    const [run] = mockAnalysisRuns();
    mockFinishRun(run.id, { result: result(first.id, first.name) });
    await act(() => app.queryClient.invalidateQueries());
    const alert = await screen.findByText(/The lawyer review could not be loaded/);
    expect(alert).toHaveTextContent(/migration 0012/);
    expect(within(alert).getByRole('button', { name: 'Try again' })).toBeVisible();
    expect(screen.queryByRole('region', { name: /Review of/ })).not.toBeInTheDocument();
  });
});

describe('The timeline and the analysis inputs', () => {
  it('does not count lawyers’ review decisions as input for an analysis', async () => {
    const c = mockApiState().cases.find((x) => x.id === CASE_ID);
    if (!c) throw new Error('no sample case');
    const caseEvents = c.timeline.length;
    c.timeline.push({
      ...c.timeline[0],
      id: 'review-entry-1',
      label: 'AI finding reviewed',
      description: 'Fact F1 of the AI analysis of 25 Oct 2026 accepted.',
      kind: 'review',
    });
    mockAnalysisAvailable();
    readyDocuments();
    renderApp(TAB, { as: ARYAN_EMAIL });
    expect(
      await screen.findByText(
        `${caseEvents} events (the latest 30 are sent; lawyers' review decisions never are)`,
      ),
    ).toBeVisible();
  });
});

describe('Exporting the case brief', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  function stubDownloads() {
    const createObjectURL = vi.fn(() => 'blob:synthetic-brief');
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL, revokeObjectURL: vi.fn() }));
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    return { createObjectURL, click };
  }

  it('is disabled until a finding is accepted, and says why', async () => {
    await openFinished();
    const button = screen.getByRole('button', { name: 'Export case brief (DOCX)' });
    expect(button).toBeDisabled();
    expect(button).toHaveAccessibleDescription(/Accept at least one finding first/);
  });

  it('downloads the brief made by the server, with the accepted findings only', async () => {
    const { createObjectURL, click } = stubDownloads();
    const { user } = await openFinished();
    await user.click(within(panel('Fact F1')).getByRole('button', { name: 'Accept' }));
    await within(panel('Fact F1')).findByText('Accepted');
    const button = screen.getByRole('button', { name: 'Export case brief (DOCX)' });
    expect(button).toBeEnabled();
    expect(button).toHaveAccessibleDescription(
      /the 1 accepted finding .* notes are never included/,
    );
    await user.click(button);
    expect(
      await screen.findByText('Brief saved as case-brief-LF-2026-0001-2026-10-25.docx.'),
    ).toBeVisible();
    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(click).toHaveBeenCalledTimes(1);
  });

  it('shows the server’s refusal', async () => {
    stubDownloads();
    const { user } = await openFinished();
    await user.click(within(panel('Fact F1')).getByRole('button', { name: 'Accept' }));
    await within(panel('Fact F1')).findByText('Accepted');
    server.use(
      http.get('*/api/cases/:id/analysis-runs/:runId/brief', () =>
        problem(409, 'no-accepted-findings', 'No finding of this analysis has been accepted yet.'),
      ),
    );
    await user.click(screen.getByRole('button', { name: 'Export case brief (DOCX)' }));
    expect(
      await screen.findByText(/No finding of this analysis has been accepted yet/),
    ).toBeVisible();
  });
});
