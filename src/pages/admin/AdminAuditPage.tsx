import { useId, useState } from 'react';
import { Link } from 'react-router-dom';
import { Loader2, ScrollText } from 'lucide-react';
import { useAuditLog } from '../../hooks/useAdmin';
import { useAuth } from '../../context/AuthContext';
import { casePath } from '../../lib/paths';
import type { AuditEvent, AuditFilters } from '../../types';
import { AdminNav } from '../../components/admin/AdminNav';
import { PageHeader } from '../../components/ui/PageHeader';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { ErrorState, LoadingState } from '../../components/ui/QueryState';

const ACTIONS = [
  { value: '', label: 'All actions' },
  { value: 'auth.', label: 'Sign-in and sign-out' },
  { value: 'case.', label: 'Cases' },
  { value: 'document.', label: 'Documents' },
  { value: 'hearing.', label: 'Hearings' },
  { value: 'client.', label: 'Clients' },
  { value: 'user.', label: 'Accounts' },
];
const OUTCOMES = [
  { value: '', label: 'Any outcome' },
  { value: 'success', label: 'Succeeded' },
  { value: 'denied', label: 'Refused' },
  { value: 'failed', label: 'Failed' },
];

function when(iso: string): string {
  return new Date(iso).toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
  });
}

function detailText(details: AuditEvent['details']): string {
  return Object.entries(details)
    .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : String(value)}`)
    .join(' · ');
}

/** The audit log, read-only (Administrators only; the server refuses anyone else). */
export function AdminAuditPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'Administrator';
  const [filters, setFilters] = useState<AuditFilters>({
    action: '',
    outcome: '',
    from: '',
    to: '',
  });
  const rangeError =
    filters.from && filters.to && filters.to < filters.from
      ? 'The end date must be on or after the start date.'
      : null;
  const log = useAuditLog(filters, { enabled: isAdmin && !rangeError });
  const ids = { action: useId(), outcome: useId(), from: useId(), to: useId() };
  const set = (key: keyof AuditFilters, value: string) =>
    setFilters((prev) => ({ ...prev, [key]: value }));

  if (!isAdmin) {
    return (
      <Card className="px-6 py-10 text-center">
        <p role="status" className="text-sm text-brand-700">
          The audit log is for administrators.
        </p>
      </Card>
    );
  }

  const events = log.data?.pages.flatMap((p) => p.events) ?? [];
  return (
    <>
      <PageHeader
        title="Audit Log"
        description="Who did what, and when: sign-ins, changes to cases, documents, hearings, clients and accounts, and refused attempts."
      />
      <AdminNav />
      <p className="mb-4 rounded-md bg-brand-100/70 px-3 py-2 text-xs text-brand-700">
        Entries cannot be changed or deleted through LexFlow, and the database rejects updates and
        deletions. This is not tamper-proof: someone with database administrator access could still
        alter the log. Passwords and session details are never recorded.
      </p>

      <Card className="mb-4 p-4">
        <div className="grid gap-3 sm:grid-cols-4">
          <div>
            <label htmlFor={ids.action} className="label-text">
              Action
            </label>
            <select
              id={ids.action}
              className="input-field"
              value={filters.action}
              onChange={(e) => set('action', e.target.value)}
            >
              {ACTIONS.map((a) => (
                <option key={a.value} value={a.value}>
                  {a.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor={ids.outcome} className="label-text">
              Outcome
            </label>
            <select
              id={ids.outcome}
              className="input-field"
              value={filters.outcome}
              onChange={(e) => set('outcome', e.target.value)}
            >
              {OUTCOMES.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor={ids.from} className="label-text">
              From
            </label>
            <input
              id={ids.from}
              type="date"
              className="input-field"
              value={filters.from}
              onChange={(e) => set('from', e.target.value)}
            />
          </div>
          <div>
            <label htmlFor={ids.to} className="label-text">
              To
            </label>
            <input
              id={ids.to}
              type="date"
              className="input-field"
              value={filters.to}
              aria-invalid={rangeError ? true : undefined}
              aria-describedby={rangeError ? `${ids.to}-error` : undefined}
              onChange={(e) => set('to', e.target.value)}
            />
          </div>
        </div>
        {rangeError && (
          <p id={`${ids.to}-error`} role="alert" className="mt-2 text-xs text-red-600">
            {rangeError}
          </p>
        )}
      </Card>

      {rangeError ? null : log.isPending ? (
        <Card>
          <LoadingState label="Loading the audit log…" />
        </Card>
      ) : log.isError && events.length === 0 ? (
        <Card>
          <ErrorState
            title="Couldn't load the audit log"
            error={log.error}
            onRetry={() => log.refetch()}
          />
        </Card>
      ) : events.length === 0 ? (
        <Card className="flex flex-col items-center px-6 py-16 text-center">
          <ScrollText className="h-10 w-10 text-brand-300" strokeWidth={1.5} aria-hidden="true" />
          <p className="mt-3 text-sm font-medium text-brand-700">No matching entries</p>
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-left text-sm">
              <thead>
                <tr className="border-b border-brand-100 bg-brand-50/60 text-xs uppercase tracking-wide text-brand-500">
                  <th className="px-4 py-3 font-semibold">When</th>
                  <th className="px-4 py-3 font-semibold">Who</th>
                  <th className="px-4 py-3 font-semibold">Action</th>
                  <th className="px-4 py-3 font-semibold">Outcome</th>
                  <th className="px-4 py-3 font-semibold">Case</th>
                  <th className="px-4 py-3 font-semibold">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-brand-100">
                {events.map((e) => (
                  <tr key={e.id}>
                    <td className="whitespace-nowrap px-4 py-2.5 text-brand-600">
                      {when(e.occurredAt)}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="text-brand-900">{e.actorName ?? 'Unknown'}</span>
                      {e.actorRole && (
                        <span className="block text-xs text-brand-500">{e.actorRole}</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs text-brand-800">{e.action}</td>
                    <td
                      className={`px-4 py-2.5 text-xs font-medium ${
                        e.outcome === 'success' ? 'text-emerald-700' : 'text-red-700'
                      }`}
                    >
                      {OUTCOMES.find((o) => o.value === e.outcome)?.label ?? e.outcome}
                    </td>
                    <td className="px-4 py-2.5 text-xs">
                      {e.caseId && e.caseNumber ? (
                        <Link to={casePath(e.caseId)} className="text-brand-700 hover:underline">
                          {e.caseNumber}
                        </Link>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-xs text-brand-600">{detailText(e.details)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {log.hasNextPage && (
            <div className="border-t border-brand-100 p-3 text-center">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => void log.fetchNextPage()}
                disabled={log.isFetchingNextPage}
              >
                {log.isFetchingNextPage && (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                )}
                Load older entries
              </Button>
            </div>
          )}
        </Card>
      )}
    </>
  );
}
