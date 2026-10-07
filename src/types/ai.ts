/**
 * Types for the AI analysis and precedent-research features.
 *
 * None of this is implemented yet. These are the shapes the case workspace
 * renders against and the contract a real AI / RAG service must fulfil — see
 * src/services/ai/aiService.ts for the integration seam.
 *
 * Every result is decision support for the advocate, never a ruling: outputs
 * carry their sources so a lawyer can verify each claim.
 */

/** Where the assistant is for a given case. */
export type AiStatus = 'not_connected' | 'idle' | 'running' | 'ready' | 'error';

/** A fact pulled from the case record or one of its documents. */
export interface ExtractedFact {
  id: string;
  statement: string;
  /** The document the fact was drawn from, so it can be checked. */
  sourceDocumentId?: string;
}

/** A question of law the case turns on. */
export interface LegalIssue {
  id: string;
  question: string;
  relatedFactIds: string[];
}

/** A historical judgment retrieved from the legal knowledge base. */
export interface Precedent {
  id: string;
  title: string;
  citation: string;
  court: string;
  year: number;
  /** Short summary of the judgment. */
  summary: string;
  /** Retrieval relevance, 0–1. */
  relevance: number;
  similarities: string[];
  differences: string[];
}

/** Something in the record that conflicts with something else. */
export interface Contradiction {
  id: string;
  description: string;
  sourceDocumentIds: string[];
}

/** The full output of analysing one case. */
export interface CaseAnalysis {
  caseId: string;
  generatedAt: string; // ISO timestamp
  facts: ExtractedFact[];
  issues: LegalIssue[];
  precedents: Precedent[];
  contradictions: Contradiction[];
  /**
   * Evidence-supported outcome assessment. Deliberately optional: a later
   * milestone, and only produced when the supporting precedents are strong.
   */
  outcomeAssessment?: {
    summary: string;
    supportingPrecedentIds: string[];
  };
}
