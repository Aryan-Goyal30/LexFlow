import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { lexflowApi } from '../services/api/lexflow';
import type { Case, NewCaseInput } from '../types';

/**
 * Server state for cases, reference data and documents (TanStack Query).
 * Pages use these hooks; the hooks use the API client. The server is the only
 * source of case data: nothing is kept in a separate client-side store.
 */

export const queryKeys = {
  cases: ['cases'] as const,
  case: (caseId: string) => ['cases', caseId] as const,
  clients: ['clients'] as const,
  advocates: ['advocates'] as const,
  upcomingHearings: (limit: number) => ['hearings', 'upcoming', limit] as const,
};

export function useCaseList() {
  return useQuery({ queryKey: queryKeys.cases, queryFn: lexflowApi.listCases });
}

export function useCase(caseId: string) {
  return useQuery({ queryKey: queryKeys.case(caseId), queryFn: () => lexflowApi.getCase(caseId) });
}

export function useClients() {
  return useQuery({ queryKey: queryKeys.clients, queryFn: lexflowApi.listClients });
}

export function useAdvocates() {
  return useQuery({ queryKey: queryKeys.advocates, queryFn: lexflowApi.listAdvocates });
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
