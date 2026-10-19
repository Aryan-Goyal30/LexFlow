import type { Case, CurrentUser } from '../types';

/**
 * What the screens show for a role. Only a convenience: the server checks every
 * action itself (see `server/lexflow/authz.py`) and refuses anything else.
 */

/** May open new cases: Administrators and Advocates. */
export function canOpenCases(user: CurrentUser | null): boolean {
  return user?.role === 'Administrator' || user?.role === 'Advocate';
}

const RELATION_LABELS: Record<Case['permissions']['relation'], string | null> = {
  admin: 'Administrator: full access',
  lead: 'Lead advocate',
  associate: 'Associate advocate on the case team',
  paralegal: 'Paralegal on the case team',
  client: 'Client',
  none: null,
};

export function relationLabel(relation: Case['permissions']['relation']): string | null {
  return RELATION_LABELS[relation];
}
