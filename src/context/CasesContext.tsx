import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import type { Case, NewCaseInput } from '../types';
import { mockCases, mockClients } from '../data/mockData';
import { generateCaseNumber } from '../lib/format';

/**
 * In-memory case store for v0.1.
 *
 * State lives in React only, seeded from mock data. Creating a case prepends it
 * so it shows immediately in the list. A later milestone swaps the internals for
 * API-backed data + caching while keeping this hook's surface stable.
 */

interface CasesContextValue {
  cases: Case[];
  getCaseById: (id: string) => Case | undefined;
  addCase: (input: NewCaseInput) => Case;
}

const CasesContext = createContext<CasesContextValue | undefined>(undefined);

export function CasesProvider({ children }: { children: ReactNode }) {
  const [cases, setCases] = useState<Case[]>(mockCases);

  const getCaseById = useCallback(
    (id: string) => cases.find((c) => c.id === id),
    [cases],
  );

  const addCase = useCallback((input: NewCaseInput): Case => {
    const client = mockClients.find((c) => c.id === input.clientId);
    const today = new Date().toISOString().slice(0, 10);

    let created!: Case;
    setCases((prev) => {
      created = {
        id: `case-${Date.now()}`,
        caseNumber: generateCaseNumber(prev.length + 1),
        title: input.title.trim(),
        status: input.status,
        priority: input.priority,
        practiceArea: input.practiceArea,
        clientId: input.clientId,
        clientName: client?.name ?? 'Unassigned Client',
        leadAttorney: input.leadAttorney,
        courtName: input.courtName?.trim() || undefined,
        opposingParty: input.opposingParty?.trim() || undefined,
        description: input.description.trim(),
        openedOn: today,
        nextHearing: input.nextHearing || undefined,
        documents: [],
        hearings: input.nextHearing
          ? [
              {
                id: `h-${Date.now()}`,
                date: input.nextHearing,
                time: '10:30',
                court: 'To be notified',
                purpose: 'First listing',
              },
            ]
          : [],
        timeline: [
          {
            id: `t-${Date.now()}`,
            date: today,
            label: 'Matter opened',
            description: 'Matter created in LexFlow.',
          },
        ],
      };
      return [created, ...prev];
    });
    return created;
  }, []);

  const value = useMemo<CasesContextValue>(
    () => ({ cases, getCaseById, addCase }),
    [cases, getCaseById, addCase],
  );

  return <CasesContext.Provider value={value}>{children}</CasesContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useCases(): CasesContextValue {
  const ctx = useContext(CasesContext);
  if (!ctx) throw new Error('useCases must be used within a CasesProvider');
  return ctx;
}
