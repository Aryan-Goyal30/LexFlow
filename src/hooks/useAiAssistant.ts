import { useCallback, useEffect, useRef, useState } from 'react';
import type { Case } from '../types';
import type { AiStatus, CaseAnalysis, Precedent } from '../types/ai';
import { aiService, AiNotConnectedError } from '../services/ai/aiService';

/**
 * Per-case AI assistant state. Pages use this hook, never the service
 * directly, so swapping in a real AI backend touches only src/services/ai.
 *
 * Guarantees, whatever the service does:
 * - while no service is connected, nothing is requested and nothing is shown;
 * - a failed request never leaves a result behind;
 * - a response that arrives after a newer request, or after the workspace has
 *   closed, is discarded;
 * - an analysis whose caseId doesn't match this case is rejected.
 */

export interface AnalysisState {
  status: AiStatus;
  result: CaseAnalysis | null;
  error: string | null;
}

export interface ResearchState {
  status: AiStatus;
  /** The query the current results (or error) belong to. */
  query: string | null;
  results: Precedent[] | null;
  error: string | null;
}

function failure(err: unknown, action: string): { status: AiStatus; error: string | null } {
  if (err instanceof AiNotConnectedError) return { status: 'not_connected', error: null };
  const detail = err instanceof Error && err.message ? ` ${err.message}` : '';
  return { status: 'error', error: `${action} failed.${detail}` };
}

export function useAiAssistant(legalCase: Case) {
  const connected = aiService.connected;
  const initialStatus: AiStatus = connected ? 'idle' : 'not_connected';

  const [analysis, setAnalysis] = useState<AnalysisState>({
    status: initialStatus,
    result: null,
    error: null,
  });
  const [research, setResearch] = useState<ResearchState>({
    status: initialStatus,
    query: null,
    results: null,
    error: null,
  });

  const analysisRequest = useRef(0);
  const researchRequest = useRef(0);
  const analysisInFlight = useRef(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const runAnalysis = useCallback(async () => {
    if (!aiService.connected) {
      setAnalysis({ status: 'not_connected', result: null, error: null });
      return;
    }
    // One analysis at a time; repeated clicks while running are ignored.
    if (analysisInFlight.current) return;
    analysisInFlight.current = true;
    const request = ++analysisRequest.current;
    setAnalysis({ status: 'running', result: null, error: null });

    try {
      const result = await aiService.analyzeCase(legalCase);
      if (!mounted.current || request !== analysisRequest.current) return;
      if (result.caseId !== legalCase.id) {
        throw new Error('The service returned an analysis for a different case.');
      }
      setAnalysis({ status: 'ready', result, error: null });
    } catch (err) {
      if (!mounted.current || request !== analysisRequest.current) return;
      setAnalysis({ result: null, ...failure(err, 'Analysis') });
    } finally {
      if (request === analysisRequest.current) analysisInFlight.current = false;
    }
  }, [legalCase]);

  const searchPrecedents = useCallback(
    async (rawQuery: string) => {
      const query = rawQuery.trim();
      if (!query) return;
      if (!aiService.connected) {
        setResearch({ status: 'not_connected', query: null, results: null, error: null });
        return;
      }
      // A new search supersedes any search still in flight.
      const request = ++researchRequest.current;
      setResearch({ status: 'running', query, results: null, error: null });

      try {
        const results = await aiService.searchPrecedents(legalCase, query);
        if (!mounted.current || request !== researchRequest.current) return;
        setResearch({ status: 'ready', query, results, error: null });
      } catch (err) {
        if (!mounted.current || request !== researchRequest.current) return;
        setResearch({ query, results: null, ...failure(err, 'Search') });
      }
    },
    [legalCase],
  );

  return { connected, analysis, research, runAnalysis, searchPrecedents };
}

export type AiAssistant = ReturnType<typeof useAiAssistant>;
