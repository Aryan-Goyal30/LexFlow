import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { lexflowApi } from '../services/api/lexflow';
import type { AdminUser, AdminUserChanges, AdminUserInput, AuditFilters } from '../types';

const USERS_KEY = ['admin', 'users'] as const;

/** Every account (Administrators only; the server refuses anyone else). */
export function useAdminUsers() {
  return useQuery({ queryKey: USERS_KEY, queryFn: lexflowApi.listUsers });
}

function useUserChange<V>(change: (variables: V) => Promise<AdminUser>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: change,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: USERS_KEY });
      // Names appear on case teams and lists.
      void queryClient.invalidateQueries({ queryKey: ['staff'] });
      void queryClient.invalidateQueries({ queryKey: ['advocates'] });
    },
  });
}

export function useCreateUser() {
  return useUserChange((input: AdminUserInput) => lexflowApi.createUser(input));
}

export function useUpdateUser() {
  return useUserChange(({ id, changes }: { id: string; changes: AdminUserChanges }) =>
    lexflowApi.updateUser(id, changes),
  );
}

export function useUserAction() {
  return useUserChange(({ id, action }: { id: string; action: 'disable' | 'enable' | 'unlock' }) =>
    lexflowApi.userAction(id, action),
  );
}

export function useResetPassword() {
  return useUserChange(({ id, password }: { id: string; password: string }) =>
    lexflowApi.resetUserPassword(id, password),
  );
}

/** The audit log, newest first; `fetchNextPage` loads older events. */
export function useAuditLog(filters: AuditFilters, { enabled = true } = {}) {
  return useInfiniteQuery({
    queryKey: ['admin', 'audit', filters],
    queryFn: ({ pageParam }) => lexflowApi.auditLog(filters, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.nextBefore ?? null,
    enabled,
  });
}
