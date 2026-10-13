/** Where a signed-in user lands by default: the case list. */
export const HOME_PATH = '/app/cases';

/**
 * The page to return to after sign-in. Only paths inside the app are
 * honoured, so a crafted link cannot send the user elsewhere.
 */
export function safeReturnPath(from: unknown): string {
  if (typeof from === 'string' && from.startsWith('/app') && !from.startsWith('//')) {
    return from;
  }
  return HOME_PATH;
}
