/** Small formatting helpers shared across pages. */

export function formatDate(iso?: string): string {
  if (!iso) return '—';
  const d = new Date(iso + (iso.length === 10 ? 'T00:00:00' : ''));
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('');
}

/** Generates a sequential-looking case number for newly created cases. */
export function generateCaseNumber(existingCount: number): string {
  const year = new Date().getFullYear();
  const seq = String(200 + existingCount).padStart(4, '0');
  return `LF-${year}-${seq}`;
}
