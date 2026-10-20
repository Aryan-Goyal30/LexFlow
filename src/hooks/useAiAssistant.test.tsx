import { act, render, renderHook, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useAiAssistant } from './useAiAssistant';
import { AiNotConnectedError } from '../services/ai/aiService';
import { AnalysisTab } from '../components/workspace/AnalysisTab';
import { sampleApiCase } from '../test/mockApi';
import type { Case } from '../types';
import type { CaseAnalysis, Precedent } from '../types/ai';

/*
 * The AI service is the external boundary, so it is the one thing faked here.
 * No real service exists yet; these tests check how the hook and the tabs
 * would treat one. All fixture data below is invented test data.
 */
const service = vi.hoisted(() => ({
  connected: true,
  analyzeCase: vi.fn(),
}));

vi.mock('../services/ai/aiService', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/ai/aiService')>();
  return { ...actual, aiService: service };
});

const legalCase: Case = sampleApiCase('case-1005');

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const testPrecedent = (id: string, title: string): Precedent => ({
  id,
  title,
  citation: `TEST-CITATION-${id}`,
  court: 'Test Court',
  year: 2000,
  summary: 'Test summary.',
  relevance: 0.5,
  similarities: [],
  differences: [],
});

const testAnalysis: CaseAnalysis = {
  caseId: legalCase.id,
  generatedAt: '2026-01-01T00:00:00Z',
  facts: [
    {
      id: 'f1',
      statement: 'Test fact drawn from a document.',
      sourceDocumentId: legalCase.documents[0].id,
    },
    { id: 'f2', statement: 'Test fact with no source.' },
  ],
  issues: [{ id: 'i1', question: 'Test legal issue?', relatedFactIds: ['f1'] }],
  precedents: [testPrecedent('p1', 'Test Precedent One')],
  contradictions: [],
  outcomeAssessment: { summary: 'TEST OUTCOME THAT MUST NOT BE SHOWN', supportingPrecedentIds: [] },
};

function Harness() {
  const ai = useAiAssistant(legalCase);
  return (
    <>
      <AnalysisTab legalCase={legalCase} ai={ai} />
    </>
  );
}

beforeEach(() => {
  service.connected = true;
});

describe('useAiAssistant with a service that is not connected', () => {
  it('never calls the service and reports not connected', async () => {
    service.connected = false;
    const { result } = renderHook(() => useAiAssistant(legalCase));

    expect(result.current.analysis.status).toBe('not_connected');
    await act(() => result.current.runAnalysis());

    expect(service.analyzeCase).not.toHaveBeenCalled();
    expect(result.current.analysis).toEqual({ status: 'not_connected', result: null, error: null });
  });

  it('treats AiNotConnectedError from the service as not connected, not as a result', async () => {
    service.analyzeCase.mockRejectedValue(new AiNotConnectedError());
    const { result } = renderHook(() => useAiAssistant(legalCase));

    await act(() => result.current.runAnalysis());
    expect(result.current.analysis).toEqual({ status: 'not_connected', result: null, error: null });
  });
});

describe('useAiAssistant error handling', () => {
  it('turns a failed analysis into an error with no result', async () => {
    service.analyzeCase.mockRejectedValue(new Error('Service unavailable (503).'));
    const { result } = renderHook(() => useAiAssistant(legalCase));

    await act(() => result.current.runAnalysis());
    expect(result.current.analysis).toEqual({
      status: 'error',
      result: null,
      error: 'Analysis failed. Service unavailable (503).',
    });
  });

  it('rejects an analysis that belongs to a different case', async () => {
    service.analyzeCase.mockResolvedValue({ ...testAnalysis, caseId: 'another-case' });
    const { result } = renderHook(() => useAiAssistant(legalCase));

    await act(() => result.current.runAnalysis());
    expect(result.current.analysis.status).toBe('error');
    expect(result.current.analysis.result).toBeNull();
    expect(result.current.analysis.error).toMatch(/different case/);
  });
});

describe('useAiAssistant stale and repeated requests', () => {
  it('ignores a second analysis request while one is running', async () => {
    const pending = deferred<CaseAnalysis>();
    service.analyzeCase.mockReturnValue(pending.promise);
    const { result } = renderHook(() => useAiAssistant(legalCase));

    let run!: Promise<void>;
    act(() => {
      run = result.current.runAnalysis();
    });
    await act(() => result.current.runAnalysis());
    expect(service.analyzeCase).toHaveBeenCalledTimes(1);

    await act(async () => {
      pending.resolve(testAnalysis);
      await run;
    });
    expect(result.current.analysis.status).toBe('ready');
  });

  it('discards a response that arrives after the workspace has closed', async () => {
    const pending = deferred<CaseAnalysis>();
    service.analyzeCase.mockReturnValue(pending.promise);
    const { result, unmount } = renderHook(() => useAiAssistant(legalCase));

    let run!: Promise<void>;
    act(() => {
      run = result.current.runAnalysis();
    });
    const lastSeen = result.current.analysis;
    unmount();
    pending.resolve(testAnalysis);
    await run;

    expect(lastSeen.status).toBe('running');
    expect(result.current.analysis.result).toBeNull();
  });
});

describe('AI tabs with a connected service', () => {
  it('shows an error and no analysis when the service fails', async () => {
    service.analyzeCase.mockRejectedValue(new Error('Service unavailable (503).'));
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole('button', { name: /Analyse case/ }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Analysis failed. Service unavailable (503). No analysis is shown.',
    );
    expect(screen.getByText('Failed')).toBeInTheDocument();
    expect(screen.queryByText(/Key Facts/)).not.toBeInTheDocument();
    expect(screen.getByText('What the analysis will contain')).toBeInTheDocument();
  });

  it('shows a returned analysis with sources, and never the outcome assessment', async () => {
    service.analyzeCase.mockResolvedValue(testAnalysis);
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole('button', { name: /Analyse case/ }));

    expect(await screen.findByText('Key Facts (2)')).toBeInTheDocument();
    expect(screen.getByText(`Source: ${legalCase.documents[0].name}`)).toBeInTheDocument();
    expect(screen.getByText('No source document cited. Verify manually.')).toBeInTheDocument();
    expect(screen.getByText('Test Precedent One')).toBeInTheDocument();
    expect(screen.queryByText(/TEST OUTCOME THAT MUST NOT BE SHOWN/)).not.toBeInTheDocument();
  });
});
