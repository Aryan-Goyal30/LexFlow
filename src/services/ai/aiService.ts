import { apiFetch } from '../api/client';
import type { AnalysisRun, AnalysisRunInput, AnalysisRunList, AnalysisSetup } from '../../types/ai';

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
};
