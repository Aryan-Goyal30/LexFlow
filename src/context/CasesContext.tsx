import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import type { Case, CaseDocument, Client, NewCaseInput } from '../types';
import { advocates as seedAdvocates, mockCases, mockClients } from '../data/mockData';
import { formatFileSize, nextCaseNumber, todayIsoDate } from '../lib/format';
import { createId } from '../lib/ids';

/**
 * In-memory case store.
 *
 * State lives in React only, seeded from mock data, so a page refresh resets
 * it. Creating a case prepends it so it shows immediately in the list.
 * Uploaded documents are held as browser object URLs; each URL is revoked when
 * its document is removed, and the browser releases the rest when the page
 * unloads. A later milestone swaps the internals for API-backed data and file
 * storage while keeping this hook's surface stable.
 */

interface CasesContextValue {
  cases: Case[];
  /** Reference data for forms. Mock data today; an API later. */
  clients: Client[];
  advocates: string[];
  getCaseById: (id: string) => Case | undefined;
  /** Creates a case, adds it to the top of the list, and returns it. */
  addCase: (input: NewCaseInput) => Case;
  /** Attaches files that have already passed the document rules. */
  addDocuments: (caseId: string, files: File[]) => CaseDocument[];
  removeDocument: (caseId: string, documentId: string) => void;
}

function documentTypeFor(file: File): string {
  const ext = file.name.split('.').pop()?.toLowerCase();
  if (ext === 'pdf') return 'PDF';
  if (ext === 'doc' || ext === 'docx') return 'Word document';
  if (ext === 'txt') return 'Text';
  if (ext && ['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(ext)) return 'Image';
  return 'File';
}

const CasesContext = createContext<CasesContextValue | undefined>(undefined);

export function CasesProvider({ children }: { children: ReactNode }) {
  const [cases, setCases] = useState<Case[]>(mockCases);
  // Case numbers handed out this session, so two cases created before a
  // re-render can never be given the same number.
  const issuedNumbers = useRef<string[]>([]);

  const getCaseById = useCallback((id: string) => cases.find((c) => c.id === id), [cases]);

  const addCase = useCallback(
    (input: NewCaseInput): Case => {
      const client = mockClients.find((c) => c.id === input.clientId);
      const today = todayIsoDate();
      const caseNumber = nextCaseNumber([
        ...cases.map((c) => c.caseNumber),
        ...issuedNumbers.current,
      ]);
      issuedNumbers.current.push(caseNumber);

      const created: Case = {
        id: createId('case'),
        caseNumber,
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
                id: createId('hearing'),
                date: input.nextHearing,
                time: '10:30',
                court: 'To be notified',
                purpose: 'First listing',
              },
            ]
          : [],
        timeline: [
          {
            id: createId('event'),
            date: today,
            label: 'Matter opened',
            description: 'Matter created in LexFlow.',
          },
        ],
      };

      setCases((prev) => [created, ...prev]);
      return created;
    },
    [cases],
  );

  const addDocuments = useCallback((caseId: string, files: File[]): CaseDocument[] => {
    const today = todayIsoDate();
    const docs: CaseDocument[] = files.map((file) => ({
      id: createId('doc'),
      name: file.name,
      type: documentTypeFor(file),
      uploadedOn: today,
      size: formatFileSize(file.size),
      url: URL.createObjectURL(file),
    }));
    setCases((prev) =>
      prev.map((c) => (c.id === caseId ? { ...c, documents: [...docs, ...c.documents] } : c)),
    );
    return docs;
  }, []);

  const removeDocument = useCallback(
    (caseId: string, documentId: string) => {
      const doc = cases.find((c) => c.id === caseId)?.documents.find((d) => d.id === documentId);
      if (doc?.url) URL.revokeObjectURL(doc.url);
      setCases((prev) =>
        prev.map((c) =>
          c.id === caseId ? { ...c, documents: c.documents.filter((d) => d.id !== documentId) } : c,
        ),
      );
    },
    [cases],
  );

  const value = useMemo<CasesContextValue>(
    () => ({
      cases,
      clients: mockClients,
      advocates: seedAdvocates,
      getCaseById,
      addCase,
      addDocuments,
      removeDocument,
    }),
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
