import { Link, useParams, useSearchParams } from 'react-router-dom';
import { ArrowLeft, BookOpenText, FileText, LayoutList, Scale, Sparkles } from 'lucide-react';
import type { Case } from '../types';
import { useCases } from '../context/CasesContext';
import { useAiAssistant } from '../hooks/useAiAssistant';
import { Card } from '../components/ui/Card';
import { StatusBadge, PriorityBadge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Tabs, type TabItem } from '../components/ui/Tabs';
import { OverviewTab } from '../components/workspace/OverviewTab';
import { DocumentsTab } from '../components/workspace/DocumentsTab';
import { AnalysisTab } from '../components/workspace/AnalysisTab';
import { ResearchTab } from '../components/workspace/ResearchTab';
import { formatDate } from '../lib/format';

type WorkspaceTab = 'overview' | 'documents' | 'analysis' | 'research';

const TAB_KEYS: WorkspaceTab[] = ['overview', 'documents', 'analysis', 'research'];

export function CaseWorkspacePage() {
  const { caseId } = useParams<{ caseId: string }>();
  const { getCaseById } = useCases();
  const legalCase = caseId ? getCaseById(caseId) : undefined;

  if (!legalCase) {
    return (
      <Card className="flex flex-col items-center justify-center px-6 py-16 text-center">
        <Scale className="h-10 w-10 text-brand-300" strokeWidth={1.5} />
        <p className="mt-3 text-sm font-medium text-brand-700">Case not found</p>
        <p className="mt-1 text-sm text-brand-500">
          This matter may have been removed or the link is incorrect.
        </p>
        <Link to="/app/cases" className="mt-4">
          <Button variant="secondary">Back to Cases</Button>
        </Link>
      </Card>
    );
  }

  // Keyed by case so AI state never leaks from one matter into another.
  return <Workspace key={legalCase.id} legalCase={legalCase} />;
}

function Workspace({ legalCase: c }: { legalCase: Case }) {
  const ai = useAiAssistant(c);
  const [params, setParams] = useSearchParams();
  const requested = params.get('tab') as WorkspaceTab | null;
  const tab: WorkspaceTab = requested && TAB_KEYS.includes(requested) ? requested : 'overview';

  const tabs: TabItem<WorkspaceTab>[] = [
    { key: 'overview', label: 'Overview', icon: LayoutList },
    { key: 'documents', label: 'Documents', icon: FileText, meta: c.documents.length },
    {
      key: 'analysis',
      label: 'AI Analysis',
      icon: Sparkles,
      meta: ai.connected ? undefined : 'Not connected',
    },
    { key: 'research', label: 'Research', icon: BookOpenText },
  ];

  return (
    <>
      <Link
        to="/app/cases"
        className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-brand-600 hover:text-brand-800"
      >
        <ArrowLeft className="h-4 w-4" />
        All Cases
      </Link>

      <header className="mb-5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-brand-400">
            {c.caseNumber}
          </span>
          <StatusBadge status={c.status} />
          <PriorityBadge priority={c.priority} />
        </div>
        <h1 className="mt-2 text-2xl font-bold text-brand-900">{c.title}</h1>
        <p className="mt-1 text-sm text-brand-500">
          {c.practiceArea} · {c.clientName} · Opened {formatDate(c.openedOn)}
          {c.nextHearing && <> · Next hearing {formatDate(c.nextHearing)}</>}
        </p>
      </header>

      <Tabs
        items={tabs}
        active={tab}
        onChange={(key) => setParams(key === 'overview' ? {} : { tab: key }, { replace: true })}
      />

      <div className="pt-6" role="tabpanel">
        {tab === 'overview' && <OverviewTab legalCase={c} />}
        {tab === 'documents' && <DocumentsTab legalCase={c} />}
        {tab === 'analysis' && <AnalysisTab legalCase={c} ai={ai} />}
        {tab === 'research' && <ResearchTab legalCase={c} ai={ai} />}
      </div>
    </>
  );
}
