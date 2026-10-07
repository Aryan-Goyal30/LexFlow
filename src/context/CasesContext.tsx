import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import type { Case, CaseDocument, NewCaseInput } from '../types';
import { mockCases, mockClients } from '../data/mockData';
import { formatFileSize, generateCaseNumber } from '../lib/format';

/**
 * In-memory case store.
 *
 * State lives in React only, seeded from mock data. Creating a case prepends it
 * so it shows immediately in the list. Uploaded documents are held as browser
 * object URLs for the session. A later milestone swaps the internals for
 * API-backed data + file storage while keeping this hook's surface stable.
 */

interface CasesContextValue {
  cases: Case[];
  getCaseById: (id: string) => Case | undefined;
  addCase: (input: NewCaseInput) => Case;
  addDocuments: (caseId: string, files: File[]) => void;
  removeDocument: (caseId: string, documentId: string) => void;
}

function documentTypeFor(file: File): string {
  const ext = file.name.split('.').pop()?.toLowerCase();
  if (ext === 'pdf') return 'PDF';
  if (ext === 'doc' || ext === 'docx') return 'Word document';
  if (ext === 'txt') return 'Text';
  if (file.type.startsWith('image/')) return 'Image';
  return 'File';
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

  const addDocuments = useCallback((caseId: string, files: File[]) => {
    const today = new Date().toISOString().slice(0, 10);
    const docs: CaseDocument[] = files.map((file, i) => ({
      id: `doc-${Date.now()}-${i}`,
      name: file.name,
      type: documentTypeFor(file),
      uploadedOn: today,
      size: formatFileSize(file.size),
      url: URL.createObjectURL(file),
    }));
    setCases((prev) =>
      prev.map((c) => (c.id === caseId ? { ...c, documents: [...docs, ...c.documents] } : c)),
    );
  }, []);

  const removeDocument = useCallback((caseId: string, documentId: string) => {
    setCases((prev) =>
      prev.map((c) => {
        if (c.id !== caseId) return c;
        const doc = c.documents.find((d) => d.id === documentId);
        if (doc?.url) URL.revokeObjectURL(doc.url);
        return { ...c, documents: c.documents.filter((d) => d.id !== documentId) };
      }),
    );
  }, []);

  const value = useMemo<CasesContextValue>(
    () => ({ cases, getCaseById, addCase, addDocuments, removeDocument }),
    [cases, getCaseById, addCase, addDocuments, removeDocument],
  );

  return <CasesContext.Provider value={value}>{children}</CasesContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useCases(): CasesContextValue {
  const ctx = useContext(CasesContext);
  if (!ctx) throw new Error('useCases must be used within a CasesProvider');
  return ctx;
}
