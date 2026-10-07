/**
 * Domain types for LexFlow.
 *
 * These describe the core entities of the case-management domain. For v0.1 they
 * back mock/in-memory data; later milestones will map them to API responses.
 */

export type UserRole = 'Administrator' | 'Advocate' | 'Paralegal' | 'Client';

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
}

export type CaseStatus = 'Open' | 'In Progress' | 'On Hold' | 'Closed';

export type CasePriority = 'Low' | 'Medium' | 'High' | 'Critical';

export type PracticeArea =
  | 'Corporate / Commercial'
  | 'Civil'
  | 'Criminal'
  | 'Family'
  | 'Intellectual Property'
  | 'Constitutional / Administrative'
  | 'Real Estate'
  | 'Employment & Labour';

export interface Client {
  id: string;
  name: string;
  email: string;
  phone: string;
  company?: string;
}

export interface CaseEvent {
  id: string;
  date: string; // ISO date
  label: string;
  description: string;
}

export interface Hearing {
  id: string;
  date: string; // ISO date
  time: string;
  court: string;
  purpose: string;
}

export interface CaseDocument {
  id: string;
  name: string;
  type: string;
  uploadedOn: string; // ISO date
  size: string;
}

export interface Case {
  id: string;
  caseNumber: string;
  title: string;
  status: CaseStatus;
  priority: CasePriority;
  practiceArea: PracticeArea;
  clientId: string;
  clientName: string;
  leadAttorney: string;
  courtName?: string;
  opposingParty?: string;
  description: string;
  openedOn: string; // ISO date
  nextHearing?: string; // ISO date
  documents: CaseDocument[];
  hearings: Hearing[];
  timeline: CaseEvent[];
}

/** Shape submitted by the "Add New Case" form. */
export interface NewCaseInput {
  title: string;
  clientId: string;
  practiceArea: PracticeArea;
  status: CaseStatus;
  priority: CasePriority;
  leadAttorney: string;
  courtName?: string;
  opposingParty?: string;
  description: string;
  nextHearing?: string;
}
