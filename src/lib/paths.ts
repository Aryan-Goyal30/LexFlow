import type { CurrentUser } from '../types';

/** Where a signed-in user lands by default: the case list. */
export const HOME_PATH = '/app/cases';

/** A case's workspace, and the page that edits its details. */
export const casePath = (caseId: string) => `/app/cases/${encodeURIComponent(caseId)}`;
export const editCasePath = (caseId: string) => `${casePath(caseId)}/edit`;

/** Clients: the list, adding one, one client, and opening a case for them. */
export const CLIENTS_PATH = '/app/clients';
export const NEW_CLIENT_PATH = '/app/clients/new';
export const clientPath = (clientId: string) => `${CLIENTS_PATH}/${encodeURIComponent(clientId)}`;
export const newCaseForClientPath = (clientId: string) =>
  `/app/cases/new?client=${encodeURIComponent(clientId)}`;

/** Where users change their password (and must, after a temporary one). */
export const CHANGE_PASSWORD_PATH = '/app/account/password';

/** The client portal (Client accounts only). */
export const PORTAL_PATH = '/portal';
export const PORTAL_PASSWORD_PATH = '/portal/account/password';
export const portalCasePath = (caseId: string) =>
  `${PORTAL_PATH}/cases/${encodeURIComponent(caseId)}`;

type Role = CurrentUser['role'] | undefined;

/** Where each kind of account lives: clients in the portal, staff in the app. */
export const homeFor = (role: Role) => (role === 'Client' ? PORTAL_PATH : HOME_PATH);
export const passwordPathFor = (role: Role) =>
  role === 'Client' ? PORTAL_PASSWORD_PATH : CHANGE_PASSWORD_PATH;

/**
 * The page to return to after sign-in. Only paths in the signed-in account's
 * own area are honoured, so a crafted link cannot send the user elsewhere (and
 * a client is never sent into the staff app, or staff into the portal).
 */
export function safeReturnPath(from: unknown, role?: Role): string {
  const area = role === 'Client' ? PORTAL_PATH : '/app';
  if (
    typeof from === 'string' &&
    (from === area || from.startsWith(`${area}/`) || from.startsWith(`${area}?`)) &&
    !from.startsWith('//')
  ) {
    return from;
  }
  return homeFor(role);
}
