import { useId, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Search, FolderOpen } from 'lucide-react';
import { useCaseList } from '../hooks/useCases';
import { useAuth } from '../context/AuthContext';
import { canOpenCases } from '../lib/roles';
import { PageHeader } from '../components/ui/PageHeader';
import { Card } from '../components/ui/Card';
import { ButtonLink } from '../components/ui/Button';
import { ArchivedBadge, StatusBadge, PriorityBadge, SampleBadge } from '../components/ui/Badge';
import { ErrorState, LoadingState, StaleDataNotice } from '../components/ui/QueryState';
import { formatDate, isPastDate } from '../lib/format';
import type { CaseStatus, CaseSummary } from '../types';

const STATUS_FILTERS: Array<CaseStatus | 'All'> = [
  'All',
  'Open',
  'In Progress',
  'On Hold',
  'Closed',
];

export function CasesPage() {
  const [showArchived, setShowArchived] = useState(false);
  const archivedToggleId = useId();
  const {
    data: cases,
    isPending,
    isError,
    error,
    refetch,
  } = useCaseList(showArchived ? 'include' : 'exclude');
  const { user } = useAuth();
  const mayOpen = canOpenCases(user);

  let description = 'Loading…';
  if (cases) {
    const archivedCount = cases.filter((c) => c.archivedAt).length;
    description = `${cases.length} matter${cases.length === 1 ? '' : 's'} on file`;
    description += showArchived ? `, ${archivedCount} of them archived.` : '.';
    if (cases.some((c) => c.isSample)) {
      description += ' Cases marked Sample are fictional, and their dates are fixed.';
    }
  }

  return (
    <>
      <PageHeader
        title="Cases"
        description={cases || isPending ? description : undefined}
        actions={
          <div className="flex items-center gap-4">
            <label
              htmlFor={archivedToggleId}
              className="inline-flex items-center gap-2 text-sm text-brand-700"
            >
              <input
                id={archivedToggleId}
                type="checkbox"
                className="h-4 w-4 rounded border-brand-300"
                checked={showArchived}
                onChange={(e) => setShowArchived(e.target.checked)}
              />
              Show archived
            </label>
            {mayOpen && (
              <ButtonLink to="/app/cases/new">
                <Plus className="h-4 w-4" aria-hidden="true" />
                New Case
              </ButtonLink>
            )}
          </div>
        }
      />

      {/* A failed refresh keeps the list on screen, with a notice. */}
      {isError && cases && (
        <StaleDataNotice error={error} onRetry={() => refetch()} className="mb-4" />
      )}

      {isPending ? (
        <Card>
          <LoadingState label="Loading cases…" />
        </Card>
      ) : !cases ? (
        <Card>
          <ErrorState title="Couldn't load the cases" error={error} onRetry={() => refetch()} />
        </Card>
      ) : cases.length === 0 ? (
        <Card className="flex flex-col items-center justify-center px-6 py-16 text-center">
          <FolderOpen className="h-10 w-10 text-brand-300" strokeWidth={1.5} aria-hidden="true" />
          <p className="mt-3 text-sm font-medium text-brand-700">No cases yet</p>
          {mayOpen ? (
            <>
              <p className="mt-1 text-sm text-brand-500">Create the first case to get started.</p>
              <ButtonLink to="/app/cases/new" variant="secondary" className="mt-4">
                New Case
              </ButtonLink>
            </>
          ) : (
            <p className="mt-1 text-sm text-brand-500">
              No cases are assigned to you yet. An advocate or administrator can add you to a case
              team.
            </p>
          )}
        </Card>
      ) : (
        <CaseTable cases={cases} />
      )}
    </>
  );
}

function CaseTable({ cases }: { cases: CaseSummary[] }) {
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<CaseStatus | 'All'>('All');
  const searchId = useId();

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return cases.filter((c) => {
      const matchesStatus = statusFilter === 'All' || c.status === statusFilter;
      const matchesQuery =
        q === '' ||
        c.title.toLowerCase().includes(q) ||
        c.caseNumber.toLowerCase().includes(q) ||
        c.clientName.toLowerCase().includes(q) ||
        c.leadAttorney.toLowerCase().includes(q);
      return matchesStatus && matchesQuery;
    });
  }, [cases, query, statusFilter]);

  return (
    <>
      <Card className="mb-4 p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative w-full sm:max-w-xs">
            <label htmlFor={searchId} className="sr-only">
              Search cases
            </label>
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-brand-400"
              aria-hidden="true"
            />
            <input
              id={searchId}
              type="search"
              placeholder="Search cases…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="input-field pl-9"
            />
          </div>

          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by status">
            {STATUS_FILTERS.map((status) => (
              <button
                key={status}
                type="button"
                aria-pressed={statusFilter === status}
                onClick={() => setStatusFilter(status)}
                className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                  statusFilter === status
                    ? 'bg-brand-800 text-white'
                    : 'bg-brand-50 text-brand-600 hover:bg-brand-100'
                }`}
              >
                {status}
              </button>
            ))}
          </div>
        </div>
      </Card>

      <Card className="overflow-hidden">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
            <FolderOpen className="h-10 w-10 text-brand-300" strokeWidth={1.5} aria-hidden="true" />
            <p className="mt-3 text-sm font-medium text-brand-700">No matching cases</p>
            <p className="mt-1 text-sm text-brand-500">
              Try a different search term or status filter.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-left text-sm">
              <thead>
                <tr className="border-b border-brand-100 bg-brand-50/60 text-xs uppercase tracking-wide text-brand-500">
                  <th className="px-5 py-3 font-semibold">Case</th>
                  <th className="px-5 py-3 font-semibold">Client</th>
                  <th className="px-5 py-3 font-semibold">Practice Area</th>
                  <th className="px-5 py-3 font-semibold">Priority</th>
                  <th className="px-5 py-3 font-semibold">Status</th>
                  <th className="px-5 py-3 font-semibold">Next Hearing</th>
                  <th className="px-5 py-3 text-right font-semibold">Docs</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-brand-100">
                {filtered.map((c) => (
                  <tr key={c.id} className="group transition hover:bg-brand-50/60">
                    <td className="px-5 py-3.5">
                      <Link to={`/app/cases/${c.id}`} className="block">
                        <span className="font-medium text-brand-900 group-hover:text-brand-700">
                          {c.title}
                        </span>
                        <span className="mt-0.5 flex items-center gap-2 text-xs text-brand-500">
                          {c.caseNumber}
                          {c.archivedAt && <ArchivedBadge />}
                          {c.isSample && <SampleBadge />}
                        </span>
                      </Link>
                    </td>
                    <td className="px-5 py-3.5 text-brand-700">{c.clientName}</td>
                    <td className="px-5 py-3.5 text-brand-700">{c.practiceArea}</td>
                    <td className="px-5 py-3.5">
                      <PriorityBadge priority={c.priority} />
                    </td>
                    <td className="px-5 py-3.5">
                      <StatusBadge status={c.status} />
                    </td>
                    <td className="px-5 py-3.5 text-brand-600">
                      {c.nextHearing ? (
                        <>
                          {formatDate(c.nextHearing)}
                          {isPastDate(c.nextHearing) && (
                            <span className="block text-xs text-brand-400">Date has passed</span>
                          )}
                        </>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-right tabular-nums text-brand-600">
                      {c.documentCount}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}
