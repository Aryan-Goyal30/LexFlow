import { apiFetch, apiFetchFile, type DownloadedFile } from '../api/client';
import type {
  AnalysisReview,
  AnalysisReviewHistory,
  AnalysisReviewInput,
  AnalysisReviewList,
  AnalysisRun,
  AnalysisRunInput,
  AnalysisRunList,
  AnalysisSetup,
} from '../../types/ai';

/**
 * The integration seam for AI case analysis (Phase 5): a client of the
 * LexFlow server, never of an AI provider.
 *
 * The browser holds no provider key and builds no prompt. The server checks
 * who may run an analysis, sends the selected case text to the configured
 * provider from its worker, validates every item of the answer against the
 * evidence it sent, and returns only what survived. The UI reaches this
 * service through the hooks in `src/hooks/useCaseAnalysis.ts`.
 *
 * Precedent search is not part of this seam: it is a plain search of the
 * judgment collection (Phase 4; src/hooks/useJudgments.ts), with no AI.
 */
export interface AiService {
  /** Whether the case can be analysed now, its documents and the provider. */
  setup(caseId: string): Promise<AnalysisSetup>;
  /** Start an analysis of the selected documents (queued on the server). */
  start(caseId: string, input: AnalysisRunInput): Promise<AnalysisRun>;
  /** The case's runs, newest first, without results. */
  listRuns(caseId: string): Promise<AnalysisRunList>;
  /** One run, with its validated result when it is ready. */
  run(caseId: string, runId: string): Promise<AnalysisRun>;
  /** Every finding of a finished run with its review decision (Phase 6). */
  reviews(caseId: string, runId: string): Promise<AnalysisReviewList>;
  /** Accept, edit, reject or clear one finding (with the version seen). */
  review(
    caseId: string,
    runId: string,
    findingId: string,
    input: AnalysisReviewInput,
  ): Promise<AnalysisReview>;
  /** Every recorded change to one finding's review, oldest first. */
  reviewHistory(caseId: string, runId: string, findingId: string): Promise<AnalysisReviewHistory>;
  /** The case brief (DOCX) with the accepted findings only, made by the server. */
  exportBrief(caseId: string, runId: string): Promise<DownloadedFile>;
}

const id = (value: string) => encodeURIComponent(value);

export const aiService: AiService = {
  setup: (caseId) => apiFetch<AnalysisSetup>(`/cases/${id(caseId)}/analysis/setup`),
  start: (caseId, input) =>
    apiFetch<AnalysisRun>(`/cases/${id(caseId)}/analysis-runs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),
  listRuns: (caseId) => apiFetch<AnalysisRunList>(`/cases/${id(caseId)}/analysis-runs`),
  run: (caseId, runId) => apiFetch<AnalysisRun>(`/cases/${id(caseId)}/analysis-runs/${id(runId)}`),
  reviews: (caseId, runId) =>
    apiFetch<AnalysisReviewList>(`/cases/${id(caseId)}/analysis-runs/${id(runId)}/reviews`),
  review: (caseId, runId, findingId, input) =>
    apiFetch<AnalysisReview>(
      `/cases/${id(caseId)}/analysis-runs/${id(runId)}/reviews/${id(findingId)}`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(input),
      },
    ),
  reviewHistory: (caseId, runId, findingId) =>
    apiFetch<AnalysisReviewHistory>(
      `/cases/${id(caseId)}/analysis-runs/${id(runId)}/reviews/${id(findingId)}/history`,
    ),
  exportBrief: (caseId, runId) =>
    apiFetchFile(`/cases/${id(caseId)}/analysis-runs/${id(runId)}/brief`),
};
