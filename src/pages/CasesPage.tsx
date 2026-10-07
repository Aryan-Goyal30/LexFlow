import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Search, FolderOpen } from 'lucide-react';
import { useCases } from '../context/CasesContext';
import { PageHeader } from '../components/ui/PageHeader';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { StatusBadge, PriorityBadge } from '../components/ui/Badge';
import { formatDate } from '../lib/format';
import type { CaseStatus } from '../types';

const STATUS_FILTERS: Array<CaseStatus | 'All'> = ['All', 'Open', 'In Progress', 'On Hold', 'Closed'];

export function CasesPage() {
  const { cases } = useCases();
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<CaseStatus | 'All'>('All');

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
      <PageHeader
        title="Cases"
        description={`${cases.length} matter${cases.length === 1 ? '' : 's'} on file`}
        actions={
          <Link to="/app/cases/new">
            <Button>
              <Plus className="h-4 w-4" />
              New Case
            </Button>
          </Link>
        }
      />

      <Card className="mb-4 p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative w-full sm:max-w-xs">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-brand-400" />
            <input
              type="text"
              placeholder="Search cases…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="input-field pl-9"
            />
          </div>

          <div className="flex flex-wrap gap-1.5">
            {STATUS_FILTERS.map((status) => (
              <button
                key={status}
                type="button"
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
            <FolderOpen className="h-10 w-10 text-brand-300" strokeWidth={1.5} />
            <p className="mt-3 text-sm font-medium text-brand-700">No matching cases</p>
            <p className="mt-1 text-sm text-brand-500">
              Try a different search term or status filter.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead>
                <tr className="border-b border-brand-100 bg-brand-50/60 text-xs uppercase tracking-wide text-brand-500">
                  <th className="px-5 py-3 font-semibold">Case</th>
                  <th className="px-5 py-3 font-semibold">Client</th>
                  <th className="px-5 py-3 font-semibold">Practice Area</th>
                  <th className="px-5 py-3 font-semibold">Priority</th>
                  <th className="px-5 py-3 font-semibold">Status</th>
                  <th className="px-5 py-3 font-semibold">Opened</th>
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
                        <span className="mt-0.5 block text-xs text-brand-500">{c.caseNumber}</span>
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
                    <td className="px-5 py-3.5 text-brand-600">{formatDate(c.openedOn)}</td>
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
