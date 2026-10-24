/**
 * The fake analysis routes for front-end tests (SYNTHETIC data only).
 *
 * Mirrors `server/lexflow/api/analysis.py`: setup, start (with the server's
 * checks, in its order), list and read. Runs never progress on their own:
 * a test finishes one with `mockFinishRun`, as the worker would.
 *
 * Phase 6: the review routes of `server/lexflow/api/reviews.py` (decisions
 * with versions and history; notes only for reviewers).
 */
import { http, HttpResponse } from 'msw';
import type {
  AnalysisDocument,
  AnalysisResult,
  AnalysisReview,
  AnalysisReviewHistoryEntry,
  AnalysisReviewInput,
  AnalysisRun,
  AnalysisRunInput,
  AnalysisSetup,
  FindingKind,
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
  /** runId -> findingId -> the stored decision (absent: unreviewed). */
  reviews: Map<string, Map<string, AnalysisReview>>;
  /** `${runId}/${findingId}` -> every change, oldest first. */
  history: Map<string, AnalysisReviewHistoryEntry[]>;
  reviewsUnavailable: boolean;
}

const LABELS = { gemini: 'Google Gemini API', scripted: 'Scripted test provider (not AI)' };
const LIMITS = { maxDocuments: 20, maxInputChars: 60000, maxPrecedents: 8, runsPerHour: 10 };

const fresh = (): AnalysisState => ({
  config: {
    available: false,
    unavailableReason: 'AI analysis is turned off on this server.',
    provider: null,
    model: null,
    sampleOnly: true,
    judgmentsAvailable: 0,
  },
  runs: [],
  nextId: 1,
  reviews: new Map(),
  history: new Map(),
  reviewsUnavailable: false,
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
  outcome: { result: AnalysisResult; changed?: string[] } | { reasonCode: string; reason: string },
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
        changed: outcome.changed ?? [],
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

function readyRun(caseId: string, runId: string): AnalysisRun | Response {
  if (state.reviewsUnavailable)
    return problem(
      503,
      'review-unavailable',
      'Reviewing findings needs a database update (migration 0012) that is not applied yet.',
    );
  const run = state.runs.find((r) => r.id === runId && r.caseId === caseId);
  if (!run)
    return problem(
      404,
      'analysis-run-not-found',
      'No analysis run with this id exists for this case.',
    );
  if (run.status !== 'ready' || !run.result)
    return problem(409, 'analysis-not-ready', 'Only a finished analysis can be reviewed.');
  return run;
}

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

interface Finding {
  kind: FindingKind;
  id: string;
  text: string;
}

function findingsOf(result: AnalysisResult | null): Finding[] {
  if (!result) return [];
  return [
    ...result.facts.map((f) => ({ kind: 'fact' as const, id: f.id, text: f.statement })),
    ...result.issues.map((i) => ({ kind: 'issue' as const, id: i.id, text: i.question })),
    ...result.precedents.map((p) => ({ kind: 'precedent' as const, id: p.id, text: p.summary })),
    ...result.contradictions.map((c) => ({
      kind: 'contradiction' as const,
      id: c.id,
      text: c.description,
    })),
  ];
}

const unreviewed = (f: Finding): AnalysisReview => ({
  findingId: f.id,
  kind: f.kind,
  status: 'unreviewed',
  reviewedText: null,
  note: null,
  version: 0,
  reviewedBy: null,
  reviewedAt: null,
});

/** Review routes answer 503, as the server does without migration 0012. */
export function mockReviewsUnavailable(): void {
  state.reviewsUnavailable = true;
}

/** Another reviewer decides on a finding (the next request with the old version gets 409). */
export function mockReviewElsewhere(
  runId: string,
  findingId: string,
  status: 'accepted' | 'rejected',
): void {
  const run = state.runs.find((r) => r.id === runId);
  const finding = findingsOf(run?.result ?? null).find((f) => f.id === findingId);
  if (!run || !finding) throw new Error(`no finding ${findingId} in ${runId}`);
  const stored = state.reviews.get(runId) ?? new Map<string, AnalysisReview>();
  const version = (stored.get(findingId)?.version ?? 0) + 1;
  const at = new Date().toISOString();
  const other = { id: 'u-other', name: 'Another Reviewer' };
  stored.set(findingId, {
    ...unreviewed(finding),
    status,
    version,
    reviewedBy: other,
    reviewedAt: at,
  });
  state.reviews.set(runId, stored);
  const key = `${runId}/${findingId}`;
  state.history.set(key, [
    ...(state.history.get(key) ?? []),
    { version, status, reviewedText: null, note: null, actor: other, occurredAt: at },
  ]);
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

    http.get('*/api/cases/:id/analysis-runs/:runId/reviews', ({ params }) => {
      const found = access(String(params.id));
      if (!found) return notFound();
      const run = readyRun(String(params.id), String(params.runId));
      if (run instanceof Response) return run;
      const stored = state.reviews.get(run.id) ?? new Map<string, AnalysisReview>();
      const notes = ADVOCATES.includes(found.rel);
      const items = findingsOf(run.result).map((f) => {
        const review = stored.get(f.id) ?? unreviewed(f);
        return notes ? review : { ...review, note: null };
      });
      const count = (s: AnalysisReview['status']) => items.filter((i) => i.status === s).length;
      return HttpResponse.json({
        runId: run.id,
        canReview: ADVOCATES.includes(found.rel) && !found.archived,
        summary: {
          total: items.length,
          unreviewed: count('unreviewed'),
          accepted: count('accepted'),
          edited: count('edited'),
          rejected: count('rejected'),
        },
        items,
      });
    }),

    http.put(
      '*/api/cases/:id/analysis-runs/:runId/reviews/:findingId',
      async ({ params, request }) => {
        const found = access(String(params.id));
        if (!found) return notFound();
        if (!ADVOCATES.includes(found.rel))
          return problem(403, 'forbidden', 'You do not have permission to do this.');
        if (found.archived) return problem(409, 'case-archived', 'This case is archived.');
        const run = readyRun(String(params.id), String(params.runId));
        if (run instanceof Response) return run;
        const finding = findingsOf(run.result).find((f) => f.id === params.findingId);
        if (!finding)
          return problem(
            404,
            'finding-not-found',
            'No finding with this id exists in this analysis.',
          );
        const body = (await request.json()) as AnalysisReviewInput;
        const wording = body.reviewedText?.trim() ?? '';
        if (body.status === 'edited' && !wording)
          return problem(422, 'reviewed-text-required', 'Enter the wording you accept.');
        if (body.status === 'edited' && wording === finding.text.trim())
          return problem(422, 'wording-unchanged', 'The wording is unchanged from the AI’s.');
        const stored = state.reviews.get(run.id) ?? new Map<string, AnalysisReview>();
        const before = stored.get(finding.id) ?? unreviewed(finding);
        if (body.expectedVersion !== before.version)
          return problem(
            409,
            'review-changed',
            `This finding was reviewed again in the meantime (now version ${before.version}). Reload it and try again.`,
          );
        const next = {
          status: body.status,
          reviewedText: body.status === 'edited' ? wording : null,
          note: body.note?.trim() || null,
        };
        if (
          next.status === before.status &&
          next.reviewedText === before.reviewedText &&
          next.note === before.note
        )
          return HttpResponse.json(before);
        const at = new Date().toISOString();
        const review: AnalysisReview = {
          ...before,
          ...next,
          version: before.version + 1,
          reviewedBy: found.actor,
          reviewedAt: at,
        };
        stored.set(finding.id, review);
        state.reviews.set(run.id, stored);
        const key = `${run.id}/${finding.id}`;
        state.history.set(key, [
          ...(state.history.get(key) ?? []),
          { version: review.version, ...next, actor: found.actor, occurredAt: at },
        ]);
        return HttpResponse.json(review);
      },
    ),

    http.get('*/api/cases/:id/analysis-runs/:runId/brief', ({ params }) => {
      const found = access(String(params.id));
      if (!found) return notFound();
      const run = readyRun(String(params.id), String(params.runId));
      if (run instanceof Response) return run;
      const stored = [...(state.reviews.get(run.id)?.values() ?? [])];
      if (!stored.some((r) => r.status === 'accepted' || r.status === 'edited'))
        return problem(
          409,
          'no-accepted-findings',
          'No finding of this analysis has been accepted yet. The brief contains only findings a lawyer accepted.',
        );
      return new HttpResponse('SYNTHETIC DOCX BYTES', {
        headers: {
          'Content-Type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          'Content-Disposition': 'attachment; filename="case-brief-LF-2026-0001-2026-10-25.docx"',
        },
      });
    }),

    http.get('*/api/cases/:id/analysis-runs/:runId/reviews/:findingId/history', ({ params }) => {
      const found = access(String(params.id));
      if (!found) return notFound();
      const run = readyRun(String(params.id), String(params.runId));
      if (run instanceof Response) return run;
      const notes = ADVOCATES.includes(found.rel);
      const items = (state.history.get(`${run.id}/${String(params.findingId)}`) ?? []).map((e) =>
        notes ? e : { ...e, note: null },
      );
      return HttpResponse.json({ findingId: params.findingId, items });
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
