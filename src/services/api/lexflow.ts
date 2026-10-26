import type {
  AdminUser,
  AdminUserChanges,
  AdminUserInput,
  AuditFilters,
  AuditPage,
  Advocate,
  ArchivedFilter,
  Case,
  CaseChanges,
  DeletedDocument,
  DocumentText,
  JudgmentDetail,
  JudgmentFacets,
  JudgmentPage,
  JudgmentSearchMode,
  JudgmentSearchResult,
  JudgmentText,
  HearingChanges,
  HearingInput,
  HearingRange,
  HearingSchedule,
  CaseDocument,
  CaseSummary,
  Client,
  ClientChanges,
  ClientDetail,
  ClientInput,
  DemoStatus,
  ClientOption,
  CurrentUser,
  NewCaseInput,
  PortalCase,
  PortalCaseDetail,
  StaffMember,
  UpcomingHearing,
} from '../../types';
import { apiFetch, apiUrl } from './client';

/** One function per API operation. Types come from the generated OpenAPI schema. */

const id = (value: string) => encodeURIComponent(value);

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

/** Filters of the judgment collection (all optional). */
export interface JudgmentFilters {
  court?: string;
  yearFrom?: number;
  yearTo?: number;
  /** genuine: from real sources only; synthetic: invented test data only. */
  origin?: JudgmentOrigin;
}

export type JudgmentOrigin = 'genuine' | 'synthetic';

/** One judgment search: what, how, which page, within which filters. */
export interface JudgmentQuery extends JudgmentFilters {
  q: string;
  mode: JudgmentSearchMode;
  page: number;
  pageSize?: number;
}

function judgmentParams(filters: JudgmentFilters, extra: Record<string, string>) {
  const params = new URLSearchParams(extra);
  if (filters.court) params.set('court', filters.court);
  if (filters.yearFrom !== undefined) params.set('yearFrom', String(filters.yearFrom));
  if (filters.yearTo !== undefined) params.set('yearTo', String(filters.yearTo));
  if (filters.origin) params.set('origin', filters.origin);
  return params;
}

export const lexflowApi = {
  me: () => apiFetch<CurrentUser>('/auth/me'),

  login: (email: string, password: string) =>
    apiFetch<CurrentUser>('/auth/login', json({ email, password })),

  logout: () => apiFetch<void>('/auth/logout', { method: 'POST' }),

  changePassword: (currentPassword: string, newPassword: string) =>
    apiFetch<CurrentUser>('/auth/password', json({ currentPassword, newPassword })),

  listCases: (archived: ArchivedFilter = 'exclude') =>
    apiFetch<CaseSummary[]>(archived === 'exclude' ? '/cases' : `/cases?archived=${archived}`),

  updateCase: (caseId: string, changes: CaseChanges) =>
    apiFetch<Case>(`/cases/${id(caseId)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(changes),
    }),

  setArchived: (caseId: string, archive: boolean) =>
    apiFetch<Case>(`/cases/${id(caseId)}/${archive ? 'archive' : 'unarchive'}`, {
      method: 'POST',
    }),

  addTeamMember: (caseId: string, userId: string) =>
    apiFetch<Case>(`/cases/${id(caseId)}/team`, json({ userId })),

  removeTeamMember: (caseId: string, userId: string) =>
    apiFetch<Case>(`/cases/${id(caseId)}/team/${id(userId)}`, { method: 'DELETE' }),

  listStaff: () => apiFetch<StaffMember[]>('/staff'),

  documentText: (documentId: string, section: number) =>
    apiFetch<DocumentText>(`/documents/${id(documentId)}/text?section=${section}`),

  judgmentFacets: () => apiFetch<JudgmentFacets>('/judgments/facets'),

  listJudgments: (filters: JudgmentFilters, page: number, pageSize = 20) =>
    apiFetch<JudgmentPage>(
      `/judgments?${judgmentParams(filters, { page: String(page), pageSize: String(pageSize) })}`,
    ),

  searchJudgments: ({ q, mode, page, pageSize = 10, ...filters }: JudgmentQuery) =>
    apiFetch<JudgmentSearchResult>(
      `/judgments/search?${judgmentParams(filters, { q, mode, page: String(page), pageSize: String(pageSize) })}`,
    ),

  judgment: (judgmentId: string) => apiFetch<JudgmentDetail>(`/judgments/${id(judgmentId)}`),

  judgmentText: (judgmentId: string, section: number) =>
    apiFetch<JudgmentText>(`/judgments/${id(judgmentId)}/text?section=${section}`),

  reprocessDocument: (documentId: string) =>
    apiFetch<CaseDocument>(`/documents/${id(documentId)}/reprocess`, { method: 'POST' }),

  listUsers: () => apiFetch<AdminUser[]>('/admin/users'),

  auditLog: (filters: AuditFilters, before: string | null) => {
    const params = new URLSearchParams({ limit: '50' });
    for (const [key, value] of Object.entries(filters)) if (value) params.set(key, value);
    if (before) params.set('before', before);
    return apiFetch<AuditPage>(`/admin/audit?${params}`);
  },

  createUser: (input: AdminUserInput) => apiFetch<AdminUser>('/admin/users', json(input)),

  updateUser: (userId: string, changes: AdminUserChanges) =>
    apiFetch<AdminUser>(`/admin/users/${id(userId)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(changes),
    }),

  userAction: (userId: string, action: 'disable' | 'enable' | 'unlock') =>
    apiFetch<AdminUser>(`/admin/users/${id(userId)}/${action}`, { method: 'POST' }),

  resetUserPassword: (userId: string, temporaryPassword: string) =>
    apiFetch<AdminUser>(`/admin/users/${id(userId)}/password`, json({ temporaryPassword })),

  shareDocument: (documentId: string, share: boolean) =>
    apiFetch<CaseDocument>(`/documents/${id(documentId)}/${share ? 'share' : 'unshare'}`, {
      method: 'POST',
    }),

  portalCases: () => apiFetch<PortalCase[]>('/portal/cases'),

  portalCase: (caseId: string) => apiFetch<PortalCaseDetail>(`/portal/cases/${id(caseId)}`),

  scheduleHearing: (caseId: string, input: HearingInput) =>
    apiFetch<Case>(`/cases/${id(caseId)}/hearings`, json(input)),

  updateHearing: (hearingId: string, changes: HearingChanges) =>
    apiFetch<Case>(`/hearings/${id(hearingId)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(changes),
    }),

  cancelHearing: (hearingId: string, reason: string) =>
    apiFetch<Case>(`/hearings/${id(hearingId)}/cancel`, json({ reason: reason || null })),

  listDeletedDocuments: (caseId: string) =>
    apiFetch<DeletedDocument[]>(`/cases/${id(caseId)}/documents/deleted`),

  restoreDocument: (documentId: string) =>
    apiFetch<CaseDocument>(`/documents/${id(documentId)}/restore`, { method: 'POST' }),

  getCase: (caseId: string) => apiFetch<Case>(`/cases/${id(caseId)}`),

  createCase: (input: NewCaseInput) =>
    apiFetch<Case>('/cases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),

  listClients: () => apiFetch<Client[]>('/clients'),

  listClientOptions: () => apiFetch<ClientOption[]>('/clients/options'),

  getClient: (clientId: string) => apiFetch<ClientDetail>(`/clients/${id(clientId)}`),

  createClient: (input: ClientInput) => apiFetch<Client>('/clients', json(input)),

  /** Whether this server runs the isolated demo database (fictional records allowed). */
  demoStatus: () => apiFetch<DemoStatus>('/demo'),

  updateClient: (clientId: string, changes: ClientChanges) =>
    apiFetch<Client>(`/clients/${id(clientId)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(changes),
    }),

  listAdvocates: () => apiFetch<Advocate[]>('/advocates'),

  hearingSchedule: ({ from, to, includeCancelled }: HearingRange) =>
    apiFetch<HearingSchedule>(
      `/hearings?${new URLSearchParams({ from, to, includeCancelled: String(includeCancelled) })}`,
    ),

  upcomingHearings: (limit: number) =>
    apiFetch<UpcomingHearing[]>(`/hearings/upcoming?limit=${limit}`),

  /** One file per request, so one bad file never blocks the others. */
  uploadDocument: (caseId: string, file: File) => {
    const body = new FormData();
    body.append('file', file);
    return apiFetch<CaseDocument>(`/cases/${id(caseId)}/documents`, { method: 'POST', body });
  },

  deleteDocument: (documentId: string) =>
    apiFetch<void>(`/documents/${id(documentId)}`, { method: 'DELETE' }),
};

/**
 * Where the browser opens a stored file. Built here rather than taken from the
 * server's `downloadUrl` (which assumes `/api`), so it honours VITE_API_BASE_URL
 * like every other request.
 */
export const documentDownloadUrl = (documentId: string) =>
  apiUrl(`/documents/${id(documentId)}/download`);
