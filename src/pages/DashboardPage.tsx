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

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-start">
        <Card>
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
  const items = [
    { label: 'Total Cases', value: cases.length, hint: 'All matters on file', icon: FolderKanban },
    { label: 'Open', value: count('Open'), hint: 'Awaiting first action', icon: Activity },
    {
      label: 'In Progress',
      value: count('In Progress'),
      hint: 'Actively worked',
      icon: CalendarClock,
    },
    { label: 'Closed', value: count('Closed'), hint: 'Resolved matters', icon: CheckCircle2 },
  ];
  return (
    <Card>
      <dl className="grid divide-y divide-brand-100 sm:grid-cols-2 sm:divide-y-0 lg:grid-cols-4 lg:divide-x">
        {items.map(({ label, value, hint, icon: Icon }, i) => (
          <div
            key={label}
            className={`flex items-start justify-between gap-3 px-6 py-5 ${i > 0 ? 'sm:[&:nth-child(n+3)]:border-t sm:[&:nth-child(n+3)]:border-brand-100 lg:[&:nth-child(n+3)]:border-t-0' : ''}`}
          >
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-brand-500">
                {label}
              </dt>
              <dd className="mt-1.5 font-sans text-3xl font-semibold tabular-nums tracking-[-0.02em] text-brand-900">
                {value}
              </dd>
              <p className="mt-1 text-xs text-brand-400">{hint}</p>
            </div>
            <Icon
              className="mt-0.5 h-5 w-5 text-accent-600"
              strokeWidth={1.75}
              aria-hidden="true"
            />
          </div>
        ))}
      </dl>
    </Card>
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
            <p className="flex items-center gap-2 text-xs font-medium tabular-nums text-accent-600">
              {c.caseNumber}
              {c.isSample && <SampleBadge />}
            </p>
            <p className="mt-0.5 truncate text-sm font-medium text-brand-900">{c.title}</p>
            <p className="mt-0.5 truncate text-xs text-brand-500">{c.clientName}</p>
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
                <Link to={`/app/cases/${h.caseId}`} className="group flex gap-3.5">
                  <time
                    dateTime={h.date}
                    className="flex h-12 w-12 shrink-0 flex-col items-center justify-center rounded-md bg-brand-900 text-white"
                  >
                    <span className="text-lg font-semibold leading-none tabular-nums">
                      {h.date.slice(8, 10)}
                    </span>
                    <span className="mt-0.5 text-[10px] font-medium uppercase tracking-wider text-brand-300">
                      {new Date(`${h.date}T00:00:00`).toLocaleString('en-IN', { month: 'short' })}
                    </span>
                  </time>
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-brand-900 group-hover:text-brand-700">
                      {h.purpose}
                    </span>
                    <span className="mt-0.5 block truncate text-xs text-brand-500">
                      {h.caseTitle}
                    </span>
                    <span className="mt-1 block text-xs text-brand-500">
                      {formatDate(h.date)} · {h.time ?? 'time to be confirmed'} · {h.court}
                    </span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}
