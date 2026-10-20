import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { aiService } from '../services/ai/aiService';
import type { Case } from '../types';
import type { AnalysisRun, AnalysisRunInput } from '../types/ai';

/**
 * AI case analysis state (Phase 5). Pages use these hooks, never the service.
 *
 * Guarantees, whatever the server or network does:
 * - a run is shown only under the key of the run that was asked for, so a
 *   slow answer for an earlier run never appears as a later one;
 * - a run that belongs to another case is rejected, not shown;
 * - a failed request never leaves a result on screen;
 * - unfinished runs are polled until they are ready or failed.
 */

const POLL_MS = 2_000;

export const analysisKeys = {
  all: (caseId: string) => ['analysis', caseId] as const,
  setup: (caseId: string, documents = '') => ['analysis', caseId, 'setup', documents] as const,
  runs: (caseId: string) => ['analysis', caseId, 'runs'] as const,
  run: (caseId: string, runId: string) => ['analysis', caseId, 'runs', runId] as const,
};

export const isActive = (run: Pick<AnalysisRun, 'status'> | undefined) =>
  run?.status === 'queued' || run?.status === 'running';

/** The documents' states, so setup is asked again whenever a document changes. */
export const documentsSignature = (legalCase: Case) =>
  legalCase.documents.map((d) => `${d.id}:${d.processing?.status ?? 'none'}`).join(',');

export function useAnalysisSetup(legalCase: Case) {
  const caseId = legalCase.id;
  return useQuery({
    queryKey: analysisKeys.setup(caseId, documentsSignature(legalCase)),
    queryFn: () => aiService.setup(caseId),
    staleTime: 0,
    retry: false,
  });
}

export function useAnalysisRuns(caseId: string) {
  return useQuery({
    queryKey: analysisKeys.runs(caseId),
    queryFn: () => aiService.listRuns(caseId),
    retry: false,
  });
}

export function useAnalysisRun(caseId: string, runId: string | null) {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: analysisKeys.run(caseId, runId ?? ''),
    queryFn: async () => {
      const run = await aiService.run(caseId, runId as string);
      if (run.caseId !== caseId || run.id !== runId) {
        throw new Error('The server returned a different analysis than the one asked for.');
      }
      if (!isActive(run)) {
        // The run finished: refresh the history and whether a new run may start.
        void queryClient.invalidateQueries({ queryKey: analysisKeys.runs(caseId), exact: true });
        void queryClient.invalidateQueries({ queryKey: ['analysis', caseId, 'setup'] });
      }
      return run;
    },
    enabled: runId !== null,
    retry: false,
    refetchInterval: (query) => (isActive(query.state.data) ? POLL_MS : false),
  });
}

export function useStartAnalysis(caseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: AnalysisRunInput) => aiService.start(caseId, input),
    onSuccess: (run) => {
      queryClient.setQueryData(analysisKeys.run(caseId, run.id), run);
      void queryClient.invalidateQueries({ queryKey: analysisKeys.runs(caseId), exact: true });
      void queryClient.invalidateQueries({ queryKey: ['analysis', caseId, 'setup'] });
    },
  });
}
