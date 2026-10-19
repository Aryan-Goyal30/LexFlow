import { Link } from 'react-router-dom';
import {
  FolderKanban,
  Activity,
  CalendarClock,
  CheckCircle2,
  Plus,
  ArrowRight,
} from 'lucide-react';
import { useCaseList, useUpcomingHearings } from '../hooks/useCases';
import { useAuth } from '../context/AuthContext';
import { PageHeader } from '../components/ui/PageHeader';
import { StatCard } from '../components/ui/StatCard';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { StatusBadge, PriorityBadge, SampleBadge } from '../components/ui/Badge';
import { ButtonLink } from '../components/ui/Button';
import { ErrorState, LoadingState, StaleDataNotice } from '../components/ui/QueryState';
import { formatDate } from '../lib/format';
import { canOpenCases } from '../lib/roles';
import type { CaseSummary } from '../types';

export function DashboardPage() {
  const { user } = useAuth();
  const firstName = user?.name.split(' ')[0] ?? 'there';

  return (
    <>
      <PageHeader
        title="Practice Overview"
        description={`Welcome back, ${firstName}. Counts and hearings across all your cases.`}
        actions={
          canOpenCases(user) && (
            <ButtonLink to="/app/cases/new">
              <Plus className="h-4 w-4" aria-hidden="true" />
              New Case
            </ButtonLink>
          )
        }
      />
      <CaseOverview />
    </>
  );
}

/** The case counts and recent cases; the hearings panel loads independently. */
function CaseOverview() {
  const { data: cases, isPending, isError, error, refetch } = useCaseList();

  return (
    <>
      {/* A failed refresh keeps the counts on screen, with a notice. */}
      {isError && cases && (
        <StaleDataNotice error={error} onRetry={() => refetch()} className="mb-4" />
      )}
      {isPending ? (
        <Card>
          <LoadingState label="Loading case counts…" />
        </Card>
      ) : !cases ? (
        <Card>
          <ErrorState title="Couldn't load the cases" error={error} onRetry={() => refetch()} />
        </Card>
      ) : (
        <Counts cases={cases} />
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader
            title="Recent Cases"
            action={
              <Link
                to="/app/cases"
                className="inline-flex items-center gap-1 text-xs font-medium text-brand-600 hover:text-brand-800"
              >
                View all <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
              </Link>
            }
          />
          {cases ? (
            <RecentCases cases={cases} />
          ) : (
            <p className="px-5 py-6 text-sm text-brand-500">
              {isPending ? 'Loading…' : 'Unavailable while the case list cannot be loaded.'}
            </p>
          )}
        </Card>
        <UpcomingHearingsPanel />
      </div>
    </>
  );
}

function Counts({ cases }: { cases: CaseSummary[] }) {
  const count = (status: CaseSummary['status']) => cases.filter((c) => c.status === status).length;
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard
        label="Total Cases"
        value={cases.length}
        icon={FolderKanban}
        hint="All matters on file"
      />
      <StatCard label="Open" value={count('Open')} icon={Activity} hint="Awaiting first action" />
      <StatCard
        label="In Progress"
        value={count('In Progress')}
        icon={CalendarClock}
        hint="Actively worked"
      />
      <StatCard
        label="Closed"
        value={count('Closed')}
        icon={CheckCircle2}
        hint="Resolved matters"
      />
    </div>
  );
}

function RecentCases({ cases }: { cases: CaseSummary[] }) {
  const recent = [...cases].sort((a, b) => b.openedOn.localeCompare(a.openedOn)).slice(0, 5);
  if (recent.length === 0) {
    return <p className="px-5 py-6 text-sm text-brand-500">No cases yet.</p>;
  }
  return (
    <div className="divide-y divide-brand-100">
      {recent.map((c) => (
        <Link
          key={c.id}
          to={`/app/cases/${c.id}`}
          className="flex items-center justify-between gap-4 px-5 py-3.5 transition hover:bg-brand-50/60"
        >
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-brand-900">{c.title}</p>
            <p className="mt-0.5 flex items-center gap-2 text-xs text-brand-500">
              {c.caseNumber} · {c.clientName}
              {c.isSample && <SampleBadge />}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <PriorityBadge priority={c.priority} />
            <StatusBadge status={c.status} />
          </div>
        </Link>
      ))}
    </div>
  );
}

function UpcomingHearingsPanel() {
  const { data: hearings, isPending, isError, error, refetch } = useUpcomingHearings(5);

  return (
    <Card>
      <CardHeader title="Upcoming Hearings" />
      <CardBody className="p-0">
        {isError && hearings && (
          <StaleDataNotice error={error} onRetry={() => refetch()} className="m-3" />
        )}
        {isPending ? (
          <LoadingState label="Loading hearings…" className="py-8" />
        ) : !hearings ? (
          <ErrorState
            title="Couldn't load hearings"
            error={error}
            onRetry={() => refetch()}
            className="py-8"
          />
        ) : hearings.length === 0 ? (
          <p className="px-5 py-6 text-sm text-brand-500">
            No upcoming hearings. Sample cases have fixed dates, so their hearings may already have
            passed.
          </p>
        ) : (
          <ul className="divide-y divide-brand-100">
            {hearings.map((h) => (
              <li key={h.id} className="px-5 py-3.5">
                <Link to={`/app/cases/${h.caseId}`} className="group block">
                  <p className="text-sm font-medium text-brand-900 group-hover:text-brand-700">
                    {h.purpose}
                  </p>
                  <p className="mt-0.5 truncate text-xs text-brand-500">{h.caseTitle}</p>
                  <p className="mt-1 text-xs font-medium text-accent-600">
                    {formatDate(h.date)} · {h.time ?? 'time to be confirmed'} · {h.court}
                  </p>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}
