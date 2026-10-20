/**
 * Types for AI case analysis (Phase 5).
 *
 * The contract is the server's: these are aliases of the types generated from
 * its OpenAPI document (`src/services/api/schema.gen.ts`, `npm run api:types`),
 * so a server change that breaks the screens fails `npm run typecheck`.
 *
 * Every item in a result was checked by the server before it was stored: a
 * fact's quote occurs in the document passage it cites, a precedent is a
 * judgment passage retrieved for that run. That is a check of provenance, not
 * of legal correctness: results are decision support for the advocate, never
 * a ruling, and there is no outcome assessment (a later, gated phase).
 */

import type { components } from '../services/api/schema.gen';

type Schemas = components['schemas'];

/** Whether a case can be analysed now, and what would be sent where. */
export type AnalysisSetup = Schemas['AnalysisSetupOut'];
export type AnalysisDocument = Schemas['AnalysisDocumentOut'];
/** Body of `POST /api/cases/{id}/analysis-runs`. */
export type AnalysisRunInput = Schemas['AnalysisRunIn'];
/** One run with its validated result (when ready). */
export type AnalysisRun = Schemas['AnalysisRunOut'];
export type AnalysisRunSummary = Schemas['AnalysisRunSummaryOut'];
export type AnalysisRunList = Schemas['AnalysisRunListOut'];
export type AnalysisStatus = AnalysisRun['status'];
export type AnalysisResult = Schemas['AnalysisResultOut'];
export type AnalysisFact = Schemas['AnalysisFactOut'];
export type AnalysisSource = Schemas['AnalysisSourceOut'];
export type AnalysisIssue = Schemas['AnalysisIssueOut'];
export type AnalysisPrecedent = Schemas['AnalysisPrecedentOut'];
export type AnalysisContradiction = Schemas['AnalysisContradictionOut'];
export type AnalysisRemoved = Schemas['AnalysisRemovedOut'];
