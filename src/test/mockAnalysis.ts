/**
 * The fake analysis routes for front-end tests (SYNTHETIC data only).
 *
 * Mirrors `server/lexflow/api/analysis.py`: setup, start (with the server's
 * checks, in its order), list and read. Runs never progress on their own:
 * a test finishes one with `mockFinishRun`, as the worker would.
 */
import { http, HttpResponse } from 'msw';
import type {
  AnalysisDocument,
  AnalysisResult,
  AnalysisRun,
  AnalysisRunInput,
  AnalysisSetup,
} from '../types/ai';

type Relation = 'admin' | 'lead' | 'associate' | 'paralegal' | 'none';

export interface AnalysisCaseAccess {
  rel: Relation;
  archived: boolean;
  isSample: boolean;
  documents: AnalysisDocument[];
  actor: { id: string; name: string } | null;
}

interface Config {
  available: boolean;
  unavailableReason: string | null;
  provider: 'gemini' | 'scripted' | null;
  model: string | null;
  sampleOnly: boolean;
  judgmentsAvailable: number;
}

interface AnalysisState {
  config: Config;
  runs: AnalysisRun[];
  nextId: number;
}

const LABELS = { gemini: 'Google Gemini API', scripted: 'Scripted test provider (not AI)' };
const LIMITS = { maxDocuments: 20, maxInputChars: 60000, maxPrecedents: 8, runsPerHour: 10 };

const fresh = (): AnalysisState => ({
  config: {
    available: false,
    unavailableReason: 'AI analysis is turned off on this server (LEXFLOW_AI_PROVIDER=disabled).',
    provider: null,
    model: null,
    sampleOnly: true,
    judgmentsAvailable: 0,
  },
  runs: [],
  nextId: 1,
});

let state = fresh();

export function resetMockAnalysis(): void {
  state = fresh();
}

/** Analysis configured as the e2e server is: the scripted provider. */
export function mockAnalysisAvailable(changes: Partial<Config> = {}): void {
  state.config = {
    ...state.config,
    available: true,
    unavailableReason: null,
    provider: 'gemini',
    model: 'test-model-1',
    ...changes,
  };
}

export function mockAnalysisRuns(): AnalysisRun[] {
  return state.runs;
}

/** Finish a run as the worker would: ready with a result, or failed with a reason. */
export function mockFinishRun(
  runId: string,
  outcome: { result: AnalysisResult } | { reasonCode: string; reason: string },
): void {
  const run = state.runs.find((r) => r.id === runId);
  if (!run) throw new Error(`no run ${runId}`);
  const now = new Date().toISOString();
  Object.assign(run, { startedAt: now, finishedAt: now });
  if ('result' in outcome) {
    Object.assign(run, {
      status: 'ready',
      result: outcome.result,
      evidence: {
        documents: 1,
        passages: 2,
        judgmentPassages: 0,
        characters: 900,
        truncated: false,
      },
    });
  } else {
    Object.assign(run, {
      status: 'failed',
      reasonCode: outcome.reasonCode,
      reason: outcome.reason,
    });
  }
}

function problem(status: number, code: string, detail: string) {
  return HttpResponse.json(
    { type: `https://lexflow.invalid/problems/${code}`, title: 'Error', status, code, detail },
    { status, headers: { 'Content-Type': 'application/problem+json' } },
  );
}

const ADVOCATES: Relation[] = ['admin', 'lead', 'associate'];
const active = (caseId: string) =>
  state.runs.find((r) => r.caseId === caseId && (r.status === 'queued' || r.status === 'running'));
const summary = ({ result: _r, evidence: _e, ...run }: AnalysisRun) => run;

function cannotRun(access: AnalysisCaseAccess, caseId: string): string | null {
  const { config } = state;
  if (!config.available) return config.unavailableReason;
  if (!ADVOCATES.includes(access.rel))
    return "Only the case's advocates and administrators may start an analysis.";
  if (access.archived) return 'This case is archived.';
  if (config.sampleOnly && !access.isSample)
    return 'Only sample (fictional) cases may be analysed on this server until a privacy, confidentiality and provider-terms review allows client material.';
  if (active(caseId)) return 'An analysis of this case is already waiting or running.';
  return null;
}

export function analysisHandlers(access: (caseId: string) => AnalysisCaseAccess | null) {
  const notFound = () => problem(404, 'case-not-found', 'No case with this id exists.');
  return [
    http.get('*/api/cases/:id/analysis/setup', ({ params }) => {
      const caseId = String(params.id);
      const found = access(caseId);
      if (!found) return notFound();
      const { config } = state;
      const reason = cannotRun(found, caseId);
      const body: AnalysisSetup = {
        available: config.available,
        unavailableReason: config.available ? null : config.unavailableReason,
        provider: config.provider,
        providerLabel: config.provider ? LABELS[config.provider] : null,
        model: config.model,
        promptVersion: 'case-analysis-v1',
        canRun: reason === null,
        cannotRunReason: reason,
        sampleOnly: config.sampleOnly,
        caseIsSample: found.isSample,
        documents: found.documents,
        judgmentsAvailable: config.judgmentsAvailable,
        limits: LIMITS,
        activeRunId: config.available ? (active(caseId)?.id ?? null) : null,
      };
      return HttpResponse.json(body);
    }),

    http.post('*/api/cases/:id/analysis-runs', async ({ params, request }) => {
      const caseId = String(params.id);
      const found = access(caseId);
      if (!found) return notFound();
      if (!ADVOCATES.includes(found.rel))
        return problem(403, 'forbidden', 'You do not have permission to do this.');
      if (found.archived) return problem(409, 'case-archived', 'This case is archived.');
      if (!state.config.available)
        return problem(503, 'analysis-unavailable', state.config.unavailableReason ?? '');
      const body = (await request.json()) as AnalysisRunInput;
      if (!body.confirmTransmission)
        return problem(422, 'confirmation-required', 'Confirm that the selected text may be sent.');
      if (state.config.sampleOnly && !found.isSample)
        return problem(403, 'client-data-not-allowed', 'Only sample cases may be analysed.');
      const ready = new Set(found.documents.filter((d) => d.eligible).map((d) => d.id));
      if (body.documentIds.length === 0 || body.documentIds.some((d) => !ready.has(d)))
        return problem(422, 'document-not-eligible', 'Select only documents whose text is ready.');
      if (active(caseId))
        return problem(
          409,
          'analysis-running',
          'An analysis of this case is already waiting or running.',
        );
      const run: AnalysisRun = {
        id: `run-${state.nextId++}`,
        caseId,
        status: 'queued',
        reasonCode: null,
        reason: null,
        provider: state.config.provider ?? 'gemini',
        model: state.config.model ?? 'test-model-1',
        promptVersion: 'case-analysis-v1',
        requestedBy: found.actor,
        documentCount: body.documentIds.length,
        createdAt: new Date().toISOString(),
        startedAt: null,
        finishedAt: null,
        evidence: null,
        result: null,
      };
      state.runs.unshift(run);
      return HttpResponse.json(run, { status: 202 });
    }),

    http.get('*/api/cases/:id/analysis-runs', ({ params }) => {
      const caseId = String(params.id);
      if (!access(caseId)) return notFound();
      return HttpResponse.json({
        items: state.runs.filter((r) => r.caseId === caseId).map(summary),
      });
    }),

    http.get('*/api/cases/:id/analysis-runs/:runId', ({ params }) => {
      const caseId = String(params.id);
      if (!access(caseId)) return notFound();
      const run = state.runs.find((r) => r.id === params.runId && r.caseId === caseId);
      return run
        ? HttpResponse.json(run)
        : problem(
            404,
            'analysis-run-not-found',
            'No analysis run with this id exists for this case.',
          );
    }),
  ];
}
