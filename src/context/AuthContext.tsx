import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import type { User } from '../types';
import { currentUser } from '../data/mockData';

/**
 * Mock authentication for v0.1.
 *
 * There is no real backend yet: any email/password is accepted and resolves to a
 * single demo user. The provider shape (user + login/logout) is what later
 * milestones will wire to a real auth service, so pages should depend on this
 * hook rather than on the mock directly.
 */

interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const STORAGE_KEY = 'lexflow.auth';

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function readStoredUser(): User | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(readStoredUser);

  const login = useCallback(async (email: string, _password: string) => {
    // Simulate a network round-trip so the UI can show a pending state.
    await new Promise((resolve) => setTimeout(resolve, 450));
    const signedIn: User = { ...currentUser, email: email.trim() || currentUser.email };
    setUser(signedIn);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(signedIn));
    } catch {
      /* storage unavailable — session stays in memory only */
    }
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, isAuthenticated: user !== null, login, logout }),
    [user, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
