import { act, screen, waitFor, within } from '@testing-library/react';
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
import { mockAnalysisAvailable, mockAnalysisRuns, mockFinishRun } from '../test/mockAnalysis';
import type { AnalysisResult } from '../types/ai';

// The AI Analysis tab against the fake analysis routes (SYNTHETIC data). The
// server's rules (access, validation, the worker) are tested in
// server/tests/test_analysis_*.py; here: what the lawyer sees and sends.

const CASE_ID = 'case-1005';
const TAB = `/app/cases/${CASE_ID}?tab=analysis`;

function sampleDocuments() {
  const c = mockApiState().cases.find((x) => x.id === CASE_ID);
  if (!c) throw new Error('no sample case');
  return c.documents;
}

function readyDocuments() {
  const [first, second] = sampleDocuments();
  mockReadyText(first.id, ['SYNTHETIC page one.', 'SYNTHETIC page two.']);
  mockReadyText(second.id, ['SYNTHETIC reply.']);
  return [first, second];
}

function result(documentId: string, documentName: string): AnalysisResult {
  return {
    facts: [
      {
        id: 'F1',
        statement: 'SYNTHETIC: the rent was agreed in writing.',
        source: {
          evidenceId: 'D2',
          documentId,
          documentName,
          chunkId: 'chunk-2',
          sectionNumber: 2,
          pageNumber: 2,
          quote: 'SYNTHETIC page two.',
        },
      },
    ],
    issues: [{ id: 'I1', question: 'Which rent applies?', factIds: ['F1'] }],
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
        passage: { chunkId: 'jc-1', sectionNumber: 3, pageNumber: 3 },
        summary: 'The written agreement governs the rent.',
        similarities: ['A written tenancy.'],
        differences: ['No notice was served.'],
      },
    ],
    contradictions: [],
    insufficientEvidence: false,
    insufficientReason: null,
    precedentsAvailable: true,
    removed: {
      count: 2,
      reasons: [
        {
          code: 'unknown-judgment',
          message: 'Cited a judgment that was not retrieved for this analysis.',
          count: 1,
        },
        {
          code: 'quote-not-found',
          message: 'Its quote does not occur in the passage it cites.',
          count: 1,
        },
      ],
    },
  };
}

async function startAnalysis(user: ReturnType<typeof renderApp>['user']) {
  await user.click(await screen.findByRole('checkbox', { name: /I confirm/ }));
  await user.click(screen.getByRole('button', { name: /Analyse case/ }));
}

describe('Starting an analysis', () => {
  it('says what is sent where, and needs explicit confirmation', async () => {
    mockAnalysisAvailable();
    const [first, second] = readyDocuments();
    renderApp(TAB, { as: ARYAN_EMAIL });

    const notice = await screen.findByRole('note', { name: 'What leaves this computer' });
    expect(notice).toHaveTextContent('Google Gemini API');
    expect(notice).toHaveTextContent('model test-model-1');
    expect(notice).toHaveTextContent('only sample (fictional) cases');
    expect(screen.getByRole('checkbox', { name: new RegExp(first.name) })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: new RegExp(second.name) })).toBeChecked();
    // Documents without text cannot be chosen.
    const third = sampleDocuments()[2];
    const blocked = screen.getByRole('checkbox', { name: new RegExp(third.name) });
    expect(blocked).toBeDisabled();
    expect(blocked).not.toBeChecked();

    const analyse = screen.getByRole('button', { name: /Analyse case/ });
    expect(analyse).toBeDisabled();
    expect(analyse).toHaveAccessibleDescription(/Confirm what will be sent/);
  });

  it('sends only the chosen documents with the confirmation, then follows the run', async () => {
    mockAnalysisAvailable();
    const [first, second] = readyDocuments();
    let sent: unknown = null;
    server.events.on('request:start', async ({ request }) => {
      if (request.method === 'POST' && request.url.endsWith('/analysis-runs')) {
        sent = await request.clone().json();
      }
    });
    const { user, queryClient } = renderApp(TAB, { as: ARYAN_EMAIL });

    await user.click(await screen.findByRole('checkbox', { name: new RegExp(second.name) }));
    await startAnalysis(user);

    expect(await screen.findByText(/Waiting for the worker/)).toBeInTheDocument();
    expect(sent).toEqual({ documentIds: [first.id], confirmTransmission: true });
    server.events.removeAllListeners();

    const [run] = mockAnalysisRuns();
    mockFinishRun(run.id, { result: result(first.id, first.name) });
    await act(() => queryClient.invalidateQueries());

    expect(await screen.findByText('SYNTHETIC: the rent was agreed in writing.')).toBeVisible();
  });

  it('offers a document as soon as its text becomes ready', async () => {
    mockAnalysisAvailable();
    const [first] = sampleDocuments();
    const { queryClient } = renderApp(TAB, { as: ARYAN_EMAIL });
    const box = await screen.findByRole('checkbox', { name: new RegExp(first.name) });
    expect(box).toBeDisabled();

    mockReadyText(first.id, ['SYNTHETIC text, extracted after the tab opened.']);
    await act(() => queryClient.invalidateQueries({ queryKey: ['cases'] }));
    await waitFor(() =>
      expect(screen.getByRole('checkbox', { name: new RegExp(first.name) })).toBeChecked(),
    );
  });

  it('shows why a paralegal cannot start one', async () => {
    mockAnalysisAvailable();
    readyDocuments();
    mockAddMember(CASE_ID, MOCK_PARALEGAL_EMAIL, 'paralegal');
    renderApp(TAB, { as: MOCK_PARALEGAL_EMAIL });
    const analyse = await screen.findByRole('button', { name: /Analyse case/ });
    expect(analyse).toBeDisabled();
    expect(analyse).toHaveAccessibleDescription(/advocates and administrators/);
  });

  it('refuses client cases while only sample cases are allowed', async () => {
    mockAnalysisAvailable();
    readyDocuments();
    const c = mockApiState().cases.find((x) => x.id === CASE_ID);
    if (c) c.isSample = false;
    renderApp(TAB, { as: ARYAN_EMAIL });
    const analyse = await screen.findByRole('button', { name: /Analyse case/ });
    expect(analyse).toHaveAccessibleDescription(/Only sample \(fictional\) cases/);
  });

  it('shows the server’s refusal and starts nothing', async () => {
    mockAnalysisAvailable();
    readyDocuments();
    server.use(
      http.post('*/api/cases/:id/analysis-runs', () =>
        problem(429, 'rate-limited', 'You can start at most 10 analyses an hour.'),
      ),
    );
    const { user } = renderApp(TAB, { as: ARYAN_EMAIL });
    await startAnalysis(user);
    expect(await screen.findByRole('alert')).toHaveTextContent('at most 10 analyses an hour');
    expect(screen.queryByText(/Key Facts/)).not.toBeInTheDocument();
  });

  it('labels the scripted test provider as not AI', async () => {
    mockAnalysisAvailable({ provider: 'scripted', model: 'scripted-v1' });
    readyDocuments();
    renderApp(TAB, { as: ARYAN_EMAIL });
    expect(await screen.findByText(/results are canned test output, not AI/)).toBeVisible();
  });
});

describe('A finished analysis', () => {
  async function openFinished(
    change?: (r: AnalysisResult) => AnalysisResult,
    changed: string[] = [],
  ) {
    mockAnalysisAvailable();
    const [first] = readyDocuments();
    const app = renderApp(TAB, { as: ARYAN_EMAIL });
    await startAnalysis(app.user);
    await screen.findByText(/Waiting for the worker/);
    const [run] = mockAnalysisRuns();
    const base = result(first.id, first.name);
    mockFinishRun(run.id, { result: change ? change(base) : base, changed });
    await act(() => app.queryClient.invalidateQueries());
    await screen.findByText('Analysis result');
    return { ...app, first };
  }

  it('links every fact to its document page and shows the verified quote', async () => {
    const { first } = await openFinished();
    expect(screen.getByText(/Key Facts \(1\)/)).toBeVisible();
    expect(screen.getByText(/“SYNTHETIC page two\.”/)).toBeVisible();
    const link = screen.getByRole('link', { name: `${first.name}, page 2` });
    expect(link).toHaveAttribute(
      'href',
      `/app/cases/${CASE_ID}/documents/${encodeURIComponent(first.id)}/text?section=2`,
    );
  });

  it('links each issue to the verified facts it rests on', async () => {
    await openFinished();
    const issue = screen.getByText(/Which rent applies\?/).closest('li');
    expect(issue).not.toBeNull();
    const factLink = within(issue as HTMLElement).getByRole('link', { name: 'F1' });
    expect(factLink).toHaveAttribute('href', '#analysis-fact-F1');
    const fact = document.getElementById('analysis-fact-F1');
    expect(fact).not.toBeNull();
    expect(within(fact as HTMLElement).getByRole('link', { name: /page 2/ })).toBeVisible();
  });

  it('links both sources of a contradiction to their document pages', async () => {
    const { first } = await openFinished((r) => ({
      ...r,
      contradictions: [
        {
          id: 'C1',
          description: 'SYNTHETIC: the first use is given as 2015 and as 2017.',
          sources: [
            {
              ...r.facts[0].source,
              evidenceId: 'D1',
              sectionNumber: 1,
              pageNumber: 1,
              quote: 'SYNTHETIC page one.',
            },
            { ...r.facts[0].source, quote: 'SYNTHETIC page two (reply).' },
          ],
        },
      ],
    }));
    expect(screen.getByText(/Contradictions \(1\)/)).toBeVisible();
    expect(screen.getByText(/the first use is given as 2015 and as 2017/)).toBeVisible();
    expect(screen.getByText(/“SYNTHETIC page one\.”/)).toBeVisible();
    expect(screen.getByText(/“SYNTHETIC page two \(reply\)\.”/)).toBeVisible();
    const base = `/app/cases/${CASE_ID}/documents/${encodeURIComponent(first.id)}/text`;
    expect(screen.getByRole('link', { name: `${first.name}, page 1` })).toHaveAttribute(
      'href',
      base, // section 1 is the document's first page: no query
    );
    // Page 2 is cited by the fact and by the contradiction: every link opens it.
    for (const link of screen.getAllByRole('link', { name: `${first.name}, page 2` })) {
      expect(link).toHaveAttribute('href', `${base}?section=2`);
    }
    expect(screen.getAllByRole('link', { name: `${first.name}, page 2` })).toHaveLength(2);
  });

  it('links each precedent to the judgment passage, labelled synthetic, with no score', async () => {
    await openFinished();
    const card = screen.getByRole('article', { name: /Asha Rao/ });
    expect(within(card).getByText('Synthetic test data')).toBeVisible();
    expect(within(card).getByRole('link', { name: /Read the passage \(page 3\)/ })).toHaveAttribute(
      'href',
      '/app/precedents/judgment-1?section=3',
    );
    expect(within(card).queryByText(/relevance/i)).not.toBeInTheDocument();
  });

  it('counts what was removed, with the reasons, and always shows the disclaimer', async () => {
    await openFinished();
    expect(
      screen.getByText(/2 items were removed because they could not be verified/),
    ).toBeVisible();
    expect(
      screen.getByText(/Cited a judgment that was not retrieved for this analysis\. \(1\)/),
    ).toBeVisible();
    expect(screen.getAllByText(/decision support for the advocate/).length).toBeGreaterThan(1);
    expect(screen.queryByText(/outcome/i)).not.toBeInTheDocument();
  });

  it('says plainly when no precedents were available', async () => {
    await openFinished((r) => ({ ...r, precedents: [], precedentsAvailable: false }));
    expect(screen.getByText(/No precedents were available for comparison/)).toBeVisible();
    expect(screen.queryByRole('article')).not.toBeInTheDocument();
  });

  it('says which sources changed after the run, and keeps the verified quotes', async () => {
    await openFinished(undefined, ['D2', 'J1']);
    const notice = screen.getByRole('status');
    expect(notice).toHaveTextContent(/Some sources changed after this analysis ran \(D2, J1\)/);
    expect(screen.getByText(/“SYNTHETIC page two\.”/)).toBeVisible();
    expect(screen.getByText('(changed since this analysis)')).toBeVisible();
  });

  it('shows no change notice while the sources are as they were', async () => {
    await openFinished();
    expect(screen.queryByText(/Some sources changed/)).not.toBeInTheDocument();
    expect(screen.queryByText('(changed since this analysis)')).not.toBeInTheDocument();
  });

  it('states insufficient evidence instead of a guess', async () => {
    await openFinished((r) => ({
      ...r,
      facts: [],
      issues: [],
      precedents: [],
      insufficientEvidence: true,
      insufficientReason: 'Nothing in the answer could be verified against the evidence.',
    }));
    expect(screen.getByText(/Not enough evidence for a useful analysis/)).toBeVisible();
    expect(screen.getByText('No verified facts.')).toBeVisible();
  });

  it('warns about document text that reads like instructions to an AI', async () => {
    const { first } = await openFinished((r) => ({
      ...r,
      instructionLikePassages: [
        {
          evidenceId: 'D1',
          documentId: r.facts[0].source.documentId,
          documentName: r.facts[0].source.documentName,
          sectionNumber: 2,
          pageNumber: 2,
        },
      ],
    }));
    const warning = screen.getByText(/Possible prompt injection/).closest('div');
    expect(warning).toHaveTextContent(/It was not used as evidence/);
    expect(within(warning as HTMLElement).getByRole('link')).toHaveAttribute(
      'href',
      `/app/cases/${CASE_ID}/documents/${encodeURIComponent(first.id)}/text?section=2`,
    );
  });

  it('shows no injection warning when nothing was flagged', async () => {
    await openFinished();
    expect(screen.queryByText(/Possible prompt injection/)).toBeNull();
  });
});

describe('Runs that fail or do not match', () => {
  it('shows a failed run’s reason and no result', async () => {
    mockAnalysisAvailable();
    readyDocuments();
    const { user, queryClient } = renderApp(TAB, { as: ARYAN_EMAIL });
    await startAnalysis(user);
    await screen.findByText(/Waiting for the worker/);
    const [run] = mockAnalysisRuns();
    mockFinishRun(run.id, {
      reasonCode: 'provider-timeout',
      reason: "Google's API did not answer in time.",
    });
    await act(() => queryClient.invalidateQueries());
    expect(
      await screen.findByText(/The analysis failed: Google's API did not answer/),
    ).toBeVisible();
    expect(screen.queryByText(/Key Facts/)).not.toBeInTheDocument();
  });

  it('rejects a run that belongs to another case', async () => {
    mockAnalysisAvailable();
    const [first] = readyDocuments();
    const { user } = renderApp(TAB, { as: ARYAN_EMAIL });
    await startAnalysis(user);
    await screen.findByText(/Waiting for the worker/);
    const [run] = mockAnalysisRuns();
    mockFinishRun(run.id, { result: result(first.id, first.name) });
    server.use(
      http.get('*/api/cases/:id/analysis-runs/:runId', () =>
        HttpResponse.json({ ...run, caseId: 'case-1001' }),
      ),
    );
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/different analysis/), {
      timeout: 5000,
    });
    expect(screen.queryByText(/Key Facts/)).not.toBeInTheDocument();
  });

  it('lists earlier runs and opens the one chosen', async () => {
    mockAnalysisAvailable();
    const [first] = readyDocuments();
    const { user, queryClient } = renderApp(TAB, { as: ARYAN_EMAIL });
    await startAnalysis(user);
    await screen.findByText(/Waiting for the worker/);
    const [older] = mockAnalysisRuns();
    mockFinishRun(older.id, { reasonCode: 'provider-timeout', reason: 'Timed out.' });
    await act(() => queryClient.invalidateQueries());
    await screen.findByText(/The analysis failed: Timed out/);

    await startAnalysis(user);
    await screen.findByText(/Waiting for the worker/);
    const [newer] = mockAnalysisRuns();
    mockFinishRun(newer.id, { result: result(first.id, first.name) });
    await act(() => queryClient.invalidateQueries());
    await screen.findByText('Analysis result');

    const history = screen.getByText('Analysis history').closest('div')
      ?.parentElement as HTMLElement;
    const entries = within(history).getAllByRole('button');
    expect(entries).toHaveLength(2);
    await user.click(entries[1]);
    expect(await screen.findByText(/The analysis failed: Timed out/)).toBeVisible();
  });
});
