import type { JudgmentSummary } from '../types';
import { formatDate } from './format';

/** The longest search the server accepts. */
export const QUERY_MAX = 300;

/** Court · date (or year) · citation, leaving out what the source did not supply. */
export function judgmentLine(j: JudgmentSummary): string {
  const when = j.decisionDate ? formatDate(j.decisionDate) : j.year ? String(j.year) : 'Undated';
  return [j.court, when, j.citation].filter(Boolean).join(' · ');
}
