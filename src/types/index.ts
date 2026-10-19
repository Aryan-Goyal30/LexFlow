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
export type ScheduledHearing = Schemas['ScheduledHearingOut'];
export type HearingSchedule = Schemas['HearingSchedule'];
export interface HearingRange {
  from: string;
  to: string;
  includeCancelled: boolean;
}
/** Body of `POST /api/cases/{id}/hearings`. */
export type HearingInput = Schemas['HearingIn'];
/** Body of `PATCH /api/hearings/{id}`: only the fields being changed. */
export type HearingChanges = Schemas['HearingUpdate'];
export type CaseEvent = Schemas['TimelineEventOut'];
export type Client = Schemas['ClientOut'];
/** A client as offered in the new-case form (no contact details). */
export type ClientOption = Schemas['ClientOption'];
/** An account as administrators see it (never any password or session detail). */
export type AdminUser = Schemas['AdminUserOut'];
export type AuditEvent = Schemas['AuditEventOut'];
export type AuditPage = Schemas['AuditPage'];
export interface AuditFilters {
  action: string;
  outcome: string;
  from: string;
  to: string;
}
export type AdminUserInput = Schemas['AdminUserCreate'];
export type AdminUserChanges = Schemas['AdminUserUpdate'];
export type PortalCase = Schemas['PortalCaseSummary'];
export type PortalCaseDetail = Schemas['PortalCaseDetail'];
/** A client's details with the cases of theirs the user may see. */
export type ClientDetail = Schemas['ClientDetail'];
export type ClientInput = Schemas['ClientIn'];
export type ClientChanges = Schemas['ClientUpdate'];
export type Advocate = Schemas['AdvocateOut'];
/** Body of `PATCH /api/cases/{id}`: only the fields being changed. */
export type CaseChanges = Schemas['CaseUpdate'];
export type TeamMember = Schemas['TeamMemberOut'];
/** A deleted document, kept until restored or purged by an operator. */
export type DeletedDocument = Schemas['DeletedDocumentOut'];
export type StaffMember = Schemas['StaffOut'];
export type ArchivedFilter = 'exclude' | 'include' | 'only';
/** Body of `POST /api/cases`. */
export type NewCaseInput = Schemas['CaseCreate'];
/** RFC 9457 problem details returned for every API error. */
export type Problem = Schemas['Problem'];

export type CaseStatus = CaseSummary['status'];
export type CasePriority = CaseSummary['priority'];
export type PracticeArea = CaseSummary['practiceArea'];

/** The signed-in user (`GET /api/auth/me`). Never includes secrets. */
export type CurrentUser = Schemas['MeOut'];
export type User = CurrentUser;
export type UserRole = CurrentUser['role'];
