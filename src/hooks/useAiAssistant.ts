import { useCallback, useState } from 'react';
import type { Case } from '../types';
import type { AiStatus, CaseAnalysis, Precedent } from '../types/ai';
import { aiService, AiNotConnectedError } from '../services/ai/aiService';

/**
 * Per-case AI assistant state. Pages use this hook, never the service
 * directly, so swapping in a real AI backend touches only src/services/ai.
 */
export function useAiAssistant(legalCase: Case) {
  const initial: AiStatus = aiService.connected ? 'idle' : 'not_connected';
  const [status, setStatus] = useState<AiStatus>(initial);
  const [analysis, setAnalysis] = useState<CaseAnalysis | null>(null);
  const [precedents, setPrecedents] = useState<Precedent[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fail = useCallback((err: unknown) => {
    if (err instanceof AiNotConnectedError) {
      setStatus('not_connected');
      return;
    }
    setStatus('error');
    setError(err instanceof Error ? err.message : 'Something went wrong.');
  }, []);

  const runAnalysis = useCallback(async () => {
    setStatus('running');
    setError(null);
    try {
      setAnalysis(await aiService.analyzeCase(legalCase));
      setStatus('ready');
    } catch (err) {
      fail(err);
    }
  }, [legalCase, fail]);

  const searchPrecedents = useCallback(
    async (query: string) => {
      setStatus('running');
      setError(null);
      try {
        setPrecedents(await aiService.searchPrecedents(legalCase, query));
        setStatus('ready');
      } catch (err) {
        fail(err);
      }
    },
    [legalCase, fail],
  );

  return {
    connected: aiService.connected,
    status,
    analysis,
    precedents,
    error,
    runAnalysis,
    searchPrecedents,
  };
}

export type AiAssistant = ReturnType<typeof useAiAssistant>;
