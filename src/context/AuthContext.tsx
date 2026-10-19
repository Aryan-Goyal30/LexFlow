import { createContext, useCallback, useContext, useEffect, useMemo, type ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { CurrentUser } from '../types';
import { ApiError, onAuthEvent } from '../services/api/client';
import { lexflowApi } from '../services/api/lexflow';

/**
 * Who is signed in, as the server says.
 *
 * The session lives in an HttpOnly cookie that scripts cannot read; the page
 * only learns the user from `GET /api/auth/me`. Nothing about the session is
 * kept in localStorage. Signing in, signing out and an ended session (any 401
 * `not-authenticated`) all start from an empty cache, so one person's cases
 * never show for the next person on the same browser.
 */

export const ME_KEY = ['auth', 'me'] as const;

// Where the Phase 1 mock sign-in kept a user. Removed so nothing reads it.
const LEGACY_STORAGE_KEY = 'lexflow.auth';

interface AuthContextValue {
  user: CurrentUser | null;
  /** 'loading' until the server has answered who is signed in. */
  status: 'loading' | 'ready' | 'error';
  error: unknown;
  retry: () => void;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<CurrentUser>;
  logout: () => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<CurrentUser>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

async function fetchCurrentUser(): Promise<CurrentUser | null> {
  try {
    return await lexflowApi.me();
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();

  useEffect(() => {
    try {
      localStorage.removeItem(LEGACY_STORAGE_KEY);
    } catch {
      /* storage unavailable: nothing to remove */
    }
  }, []);

  const me = useQuery({
    queryKey: ME_KEY,
    queryFn: fetchCurrentUser,
    staleTime: Infinity,
    retry: false,
  });

  /** Forget everything fetched for the previous user, then record the new one. */
  const startOver = useCallback(
    (user: CurrentUser | null) => {
      void queryClient.cancelQueries();
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== ME_KEY[0] });
      queryClient.getMutationCache().clear();
      queryClient.setQueryData(ME_KEY, user);
    },
    [queryClient],
  );

  useEffect(
    () =>
      onAuthEvent((event) => {
        if (event === 'unauthenticated') startOver(null);
        else void queryClient.invalidateQueries({ queryKey: ME_KEY });
      }),
    [queryClient, startOver],
  );

  const login = useCallback(
    async (email: string, password: string) => {
      const user = await lexflowApi.login(email, password);
      startOver(user);
      return user;
    },
    [startOver],
  );

  const logout = useCallback(async () => {
    try {
      await lexflowApi.logout();
    } finally {
      startOver(null);
    }
  }, [startOver]);

  const changePassword = useCallback(
    async (currentPassword: string, newPassword: string) => {
      const user = await lexflowApi.changePassword(currentPassword, newPassword);
      queryClient.setQueryData(ME_KEY, user);
      return user;
    },
    [queryClient],
  );

  const user = me.data ?? null;
  const status: AuthContextValue['status'] = me.isPending
    ? 'loading'
    : me.isError
      ? 'error'
      : 'ready';
  const { refetch } = me;
  const retry = useCallback(() => void refetch(), [refetch]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      status,
      error: me.error,
      retry,
      isAuthenticated: user !== null,
      login,
      logout,
      changePassword,
    }),
    [user, status, me.error, retry, login, logout, changePassword],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
