import type { CasePriority, CaseStatus, PracticeArea } from '../types';

/** The choices the case forms offer (the API accepts exactly these). */

export const PRACTICE_AREAS: PracticeArea[] = [
  'Corporate / Commercial',
  'Civil',
  'Criminal',
  'Family',
  'Intellectual Property',
  'Constitutional / Administrative',
  'Real Estate',
  'Employment & Labour',
];
export const STATUSES: CaseStatus[] = ['Open', 'In Progress', 'On Hold', 'Closed'];
export const PRIORITIES: CasePriority[] = ['Low', 'Medium', 'High', 'Critical'];
