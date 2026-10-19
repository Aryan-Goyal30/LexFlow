import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { lexflowApi } from '../services/api/lexflow';
import type {
  ArchivedFilter,
  Case,
  CaseChanges,
  Client,
  ClientChanges,
  ClientInput,
  HearingChanges,
  HearingInput,
  HearingRange,
  NewCaseInput,
} from '../types';

/**
 * Server state for cases, reference data and documents (TanStack Query).
 * Pages use these hooks; the hooks use the API client. The server is the only
 * source of case data: nothing is kept in a separate client-side store.
 */

export const queryKeys = {
  cases: ['cases'] as const,
  caseList: (archived: ArchivedFilter) =>
    archived === 'exclude' ? (['cases'] as const) : (['cases', 'list', archived] as const),
  staff: ['staff'] as const,
  case: (caseId: string) => ['cases', caseId] as const,
  // Under the case's key, so refreshing the case refreshes it too.
  deletedDocuments: (caseId: string) => ['cases', caseId, 'deleted-documents'] as const,
  clients: ['clients'] as const,
  clientOptions: ['clients', 'options'] as const,
  client: (clientId: string) => ['clients', 'detail', clientId] as const,
  advocates: ['advocates'] as const,
  upcomingHearings: (limit: number) => ['hearings', 'upcoming', limit] as const,
};

export function useCaseList(archived: ArchivedFilter = 'exclude') {
  return useQuery({
    queryKey: queryKeys.caseList(archived),
    queryFn: () => lexflowApi.listCases(archived),
  });
}

export function useCase(caseId: string) {
  return useQuery({ queryKey: queryKeys.case(caseId), queryFn: () => lexflowApi.getCase(caseId) });
}

export function useClients() {
  return useQuery({ queryKey: queryKeys.clients, queryFn: lexflowApi.listClients });
}

/** Every client, names only: the choices when opening a case. */
export function useClientOptions({ enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.clientOptions,
    queryFn: lexflowApi.listClientOptions,
    enabled,
  });
}

export function useAdvocates({ enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({ queryKey: queryKeys.advocates, queryFn: lexflowApi.listAdvocates, enabled });
}

export function useUpcomingHearings(limit = 5) {
  return useQuery({
    queryKey: queryKeys.upcomingHearings(limit),
    queryFn: () => lexflowApi.upcomingHearings(limit),
  });
}

export function useCreateCase() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: NewCaseInput) => lexflowApi.createCase(input),
    onSuccess: (created: Case) => {
      queryClient.setQueryData(queryKeys.case(created.id), created);
      void queryClient.invalidateQueries({ queryKey: queryKeys.cases, exact: true });
      void queryClient.invalidateQueries({ queryKey: ['hearings'] });
    },
  });
}

/** Refresh everything that shows a case's documents. */
function useRefreshCase(caseId: string) {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.case(caseId) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.cases, exact: true }),
    ]);
}

export function useUploadDocument(caseId: string) {
  const refresh = useRefreshCase(caseId);
  return useMutation({
    mutationFn: (file: File) => lexflowApi.uploadDocument(caseId, file),
    onSettled: refresh,
  });
}

export function useDeleteDocument(caseId: string) {
  const refresh = useRefreshCase(caseId);
  return useMutation({
    mutationFn: (documentId: string) => lexflowApi.deleteDocument(documentId),
    onSettled: refresh,
  });
}

/** Who can join a case team (active Advocates and Paralegals). */
export function useStaff({ enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({ queryKey: queryKeys.staff, queryFn: lexflowApi.listStaff, enabled });
}

/**
 * A change to one case (details, status, archive, team). The server answers
 * with the updated case; every list that might show it is refreshed.
 */
function useCaseChange<V>(caseId: string, change: (variables: V) => Promise<Case>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: change,
    onSuccess: (updated: Case) => {
      queryClient.setQueryData(queryKeys.case(caseId), updated);
      void queryClient.invalidateQueries({
        predicate: (q) =>
          q.queryKey[0] === 'hearings' ||
          q.queryKey[0] === 'clients' ||
          (q.queryKey[0] === 'cases' && q.queryKey[1] !== caseId),
      });
    },
  });
}

export function useUpdateCase(caseId: string) {
  return useCaseChange(caseId, (changes: CaseChanges) => lexflowApi.updateCase(caseId, changes));
}

export function useSetArchived(caseId: string) {
  return useCaseChange(caseId, (archive: boolean) => lexflowApi.setArchived(caseId, archive));
}

export function useAddTeamMember(caseId: string) {
  return useCaseChange(caseId, (userId: string) => lexflowApi.addTeamMember(caseId, userId));
}

export function useRemoveTeamMember(caseId: string) {
  return useCaseChange(caseId, (userId: string) => lexflowApi.removeTeamMember(caseId, userId));
}

/** A case's deleted documents (for the Administrator or the lead advocate). */
export function useDeletedDocuments(
  caseId: string,
  { enabled = true }: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: queryKeys.deletedDocuments(caseId),
    queryFn: () => lexflowApi.listDeletedDocuments(caseId),
    enabled,
  });
}

export function useRestoreDocument(caseId: string) {
  const refresh = useRefreshCase(caseId);
  return useMutation({
    mutationFn: (documentId: string) => lexflowApi.restoreDocument(documentId),
    onSettled: refresh,
  });
}

export function useScheduleHearing(caseId: string) {
  return useCaseChange(caseId, (input: HearingInput) => lexflowApi.scheduleHearing(caseId, input));
}

export function useUpdateHearing(caseId: string) {
  return useCaseChange(caseId, ({ id, changes }: { id: string; changes: HearingChanges }) =>
    lexflowApi.updateHearing(id, changes),
  );
}

export function useCancelHearing(caseId: string) {
  return useCaseChange(caseId, ({ id, reason }: { id: string; reason: string }) =>
    lexflowApi.cancelHearing(id, reason),
  );
}

export function useClient(clientId: string) {
  return useQuery({
    queryKey: queryKeys.client(clientId),
    queryFn: () => lexflowApi.getClient(clientId),
  });
}

/** Adding or changing a client refreshes every client list and the case lists. */
function useClientChange<V>(change: (variables: V) => Promise<Client>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: change,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.clients });
      void queryClient.invalidateQueries({ queryKey: queryKeys.cases });
    },
  });
}

export function useCreateClient() {
  return useClientChange((input: ClientInput) => lexflowApi.createClient(input));
}

export function useUpdateClient(clientId: string) {
  return useClientChange((changes: ClientChanges) => lexflowApi.updateClient(clientId, changes));
}

/** Hearings across the user's cases in a date range (refreshed by any case change). */
export function useHearingSchedule(range: HearingRange, { enabled = true } = {}) {
  return useQuery({
    queryKey: ['hearings', 'schedule', range.from, range.to, range.includeCancelled],
    queryFn: () => lexflowApi.hearingSchedule(range),
    enabled,
  });
}

/** Share a document with the case's client, or stop sharing it. */
export function useShareDocument(caseId: string) {
  const refresh = useRefreshCase(caseId);
  return useMutation({
    mutationFn: ({ id, share }: { id: string; share: boolean }) =>
      lexflowApi.shareDocument(id, share),
    onSettled: refresh,
  });
}

/** Client portal: the signed-in client's cases. */
export function usePortalCases() {
  return useQuery({ queryKey: ['portal', 'cases'], queryFn: lexflowApi.portalCases });
}

export function usePortalCase(caseId: string) {
  return useQuery({
    queryKey: ['portal', 'cases', caseId],
    queryFn: () => lexflowApi.portalCase(caseId),
  });
}
