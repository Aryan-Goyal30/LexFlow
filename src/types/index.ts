/**
 * Domain types for LexFlow.
 *
 * Case data comes from the API, so these are aliases of the types generated
 * from its OpenAPI document (`src/services/api/schema.gen.ts`, regenerated with
 * `npm run api:types`). A server change that breaks the front end therefore
 * fails `npm run typecheck`. Dates are ISO `YYYY-MM-DD` strings; ids are UUIDs.
 */

import type { components } from '../services/api/schema.gen';

type Schemas = components['schemas'];

/** One row of the case list. */
export type CaseSummary = Schemas['CaseSummary'];
/** A case with its documents, hearings and timeline (the workspace). */
export type Case = Schemas['CaseDetail'];
export type CaseDocument = Schemas['DocumentOut'];
export type Hearing = Schemas['HearingOut'];
export type UpcomingHearing = Schemas['UpcomingHearingOut'];
export type CaseEvent = Schemas['TimelineEventOut'];
export type Client = Schemas['ClientOut'];
export type Advocate = Schemas['AdvocateOut'];
/** Body of `POST /api/cases`. */
export type NewCaseInput = Schemas['CaseCreate'];
/** RFC 9457 problem details returned for every API error. */
export type Problem = Schemas['Problem'];

export type CaseStatus = CaseSummary['status'];
export type CasePriority = CaseSummary['priority'];
export type PracticeArea = CaseSummary['practiceArea'];

// The simulated sign-in (Phase 1 has no real authentication).
export type UserRole = 'Administrator' | 'Advocate' | 'Paralegal' | 'Client';

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
}
