import type { Case } from '../../types';
import type { CaseAnalysis } from '../../types/ai';

/**
 * The integration seam for the AI / RAG pipeline.
 *
 * The UI only talks to this interface (through the useAiAssistant hook). Today
 * the only implementation is `notConnectedService`, which never fabricates
 * output — it reports that no AI is connected. Integrating a real pipeline
 * means writing a new implementation of `AiService` (calling a backend that
 * does retrieval over the legal knowledge base + model inference) and
 * exporting it below. No page or component changes.
 *
 * Precedent search is not part of this seam: it is a real search of the
 * judgment collection (Phase 4; src/hooks/useJudgments.ts), with no AI.
 */
export interface AiService {
  /** False until a real backend is configured. */
  readonly connected: boolean;
  /** Extract facts and issues, retrieve precedents, flag contradictions. */
  analyzeCase(legalCase: Case): Promise<CaseAnalysis>;
}

export class AiNotConnectedError extends Error {
  constructor() {
    super('No AI service is connected in this build.');
    this.name = 'AiNotConnectedError';
  }
}

const notConnectedService: AiService = {
  connected: false,
  analyzeCase: () => Promise.reject(new AiNotConnectedError()),
};

export const aiService: AiService = notConnectedService;
