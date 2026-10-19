import type {
  Advocate,
  Case,
  CaseDocument,
  CaseSummary,
  Client,
  NewCaseInput,
  UpcomingHearing,
} from '../../types';
import { apiFetch, apiUrl } from './client';

/** One function per API operation. Types come from the generated OpenAPI schema. */

const id = (value: string) => encodeURIComponent(value);

export const lexflowApi = {
  listCases: () => apiFetch<CaseSummary[]>('/cases'),

  getCase: (caseId: string) => apiFetch<Case>(`/cases/${id(caseId)}`),

  createCase: (input: NewCaseInput) =>
    apiFetch<Case>('/cases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),

  listClients: () => apiFetch<Client[]>('/clients'),

  listAdvocates: () => apiFetch<Advocate[]>('/advocates'),

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
