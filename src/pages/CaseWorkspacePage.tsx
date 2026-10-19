import { useCallback, useEffect, useId } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { ArrowLeft, BookOpenText, FileText, LayoutList, Scale, Sparkles } from 'lucide-react';
import type { Case } from '../types';
import { useCase } from '../hooks/useCases';
import { useAiAssistant } from '../hooks/useAiAssistant';
import { ApiError } from '../services/api/client';
import { Card } from '../components/ui/Card';
import { StatusBadge, PriorityBadge, SampleBadge } from '../components/ui/Badge';
import { ErrorState, LoadingState, StaleDataNotice } from '../components/ui/QueryState';
import { ButtonLink } from '../components/ui/Button';
import { Tabs, type TabItem } from '../components/ui/Tabs';
import { tabId, tabPanelId } from '../components/ui/tabIds';
import { OverviewTab } from '../components/workspace/OverviewTab';
import { DocumentsTab } from '../components/workspace/DocumentsTab';
import { AnalysisTab } from '../components/workspace/AnalysisTab';
import { ResearchTab } from '../components/workspace/ResearchTab';
import { formatDate, isPastDate } from '../lib/format';
import { HOME_PATH } from '../lib/paths';

type WorkspaceTab = 'overview' | 'documents' | 'analysis' | 'research';

const TAB_KEYS: readonly string[] = ['overview', 'documents', 'analysis', 'research'];

function isWorkspaceTab(value: string | null): value is WorkspaceTab {
  return value !== null && TAB_KEYS.includes(value);
}

export function CaseWorkspacePage() {
  const { caseId = '' } = useParams<{ caseId: string }>();
  const { data: legalCase, isPending, isError, error, refetch } = useCase(caseId);

  if (isPending) {
    return (
      <Card>
        <LoadingState label="Loading the case…" />
      </Card>
    );
  }

  const notFound = error instanceof ApiError && error.isNotFound;
  // A failed refresh keeps the case on screen (see below); only a case that
  // never loaded, or no longer exists, is replaced by an error.
  if (!legalCase || notFound) {
    if (notFound) {
      return (
        <Card className="flex flex-col items-center justify-center px-6 py-16 text-center">
          <Scale className="h-10 w-10 text-brand-300" strokeWidth={1.5} aria-hidden="true" />
          <h1 className="mt-3 text-sm font-medium text-brand-700">Case not found</h1>
          <p className="mt-1 max-w-md text-sm text-brand-500">
            The link may be wrong, or the case no longer exists.
          </p>
          <ButtonLink to={HOME_PATH} variant="secondary" className="mt-4">
            Back to Cases
          </ButtonLink>
        </Card>
      );
    }
    return (
      <Card>
        <ErrorState title="Couldn't load the case" error={error} onRetry={() => refetch()} />
      </Card>
    );
  }

  return (
    <>
      {isError && <StaleDataNotice error={error} onRetry={() => refetch()} className="mb-4" />}
      {/* Keyed by case so AI state never leaks from one matter into another. */}
      <Workspace key={legalCase.id} legalCase={legalCase} />
    </>
  );
}

function Workspace({ legalCase: c }: { legalCase: Case }) {
  const ai = useAiAssistant(c);
  const idBase = useId();
  const [params, setParams] = useSearchParams();
  const requested = params.get('tab');
  const tab: WorkspaceTab = isWorkspaceTab(requested) ? requested : 'overview';

  // An unknown ?tab= value shows Overview; tidy the address bar to match,
  // replacing the entry so Back doesn't return to the broken URL.
  useEffect(() => {
    if (requested !== null && !isWorkspaceTab(requested)) {
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.delete('tab');
          return next;
        },
        { replace: true },
      );
    }
  }, [requested, setParams]);

  // Each tab change is a history entry, so Back and Forward move between tabs.
  // Re-selecting the current tab adds nothing.
  const selectTab = useCallback(
    (key: WorkspaceTab) => {
      if (key === tab) return;
      setParams((prev) => {
        const next = new URLSearchParams(prev);
        if (key === 'overview') next.delete('tab');
        else next.set('tab', key);
        return next;
      });
    },
    [tab, setParams],
  );

  const notConnected = ai.connected ? undefined : 'Not connected';
  const tabs: TabItem<WorkspaceTab>[] = [
    { key: 'overview', label: 'Overview', icon: LayoutList },
    { key: 'documents', label: 'Documents', icon: FileText, meta: c.documents.length },
    { key: 'analysis', label: 'AI Analysis', icon: Sparkles, meta: notConnected },
    { key: 'research', label: 'Research', icon: BookOpenText, meta: notConnected },
  ];

  return (
    <>
      <Link
        to={HOME_PATH}
        className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-brand-600 hover:text-brand-800"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        All Cases
      </Link>

      <header className="mb-5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-brand-400">
            {c.caseNumber}
          </span>
          <StatusBadge status={c.status} />
          <PriorityBadge priority={c.priority} />
          {c.isSample && <SampleBadge />}
        </div>
        <h1 className="mt-2 text-2xl font-bold text-brand-900">{c.title}</h1>
        <p className="mt-1 text-sm text-brand-500">
          {c.practiceArea} · {c.clientName} · Opened {formatDate(c.openedOn)}
          {c.nextHearing && (
            <>
              {' '}
              · Next hearing {formatDate(c.nextHearing)}
              {isPastDate(c.nextHearing) && ' (date has passed)'}
            </>
          )}
        </p>
      </header>

      <Tabs items={tabs} active={tab} onChange={selectTab} idBase={idBase} label="Case workspace" />

      <div
        className="pt-6"
        role="tabpanel"
        id={tabPanelId(idBase)}
        aria-labelledby={tabId(idBase, tab)}
        tabIndex={0}
      >
        {tab === 'overview' && <OverviewTab legalCase={c} />}
        {/* Kept mounted while hidden, so an upload still running when the user
            switches tabs keeps its progress and results, and stays "busy". */}
        <div hidden={tab !== 'documents'}>
          <DocumentsTab legalCase={c} />
        </div>
        {tab === 'analysis' && <AnalysisTab legalCase={c} ai={ai} />}
        {tab === 'research' && <ResearchTab legalCase={c} ai={ai} />}
      </div>
    </>
  );
}
