let sequence = 0;

/**
 * An id that is unique for this browser session. The counter alone guarantees
 * uniqueness, even for several ids created in the same millisecond; the time
 * and random parts keep ids from different sessions apart.
 */
export function createId(prefix: string): string {
  sequence += 1;
  const random = Math.random().toString(36).slice(2, 8);
  return `${prefix}-${Date.now().toString(36)}-${sequence.toString(36)}-${random}`;
}
