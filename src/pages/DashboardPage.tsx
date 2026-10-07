import { Link } from 'react-router-dom';
import { FolderKanban, Activity, CalendarClock, CheckCircle2, Plus, ArrowRight } from 'lucide-react';
import { useCases } from '../context/CasesContext';
import { useAuth } from '../context/AuthContext';
import { PageHeader } from '../components/ui/PageHeader';
import { StatCard } from '../components/ui/StatCard';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { StatusBadge, PriorityBadge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { formatDate } from '../lib/format';

export function DashboardPage() {
  const { cases } = useCases();
  const { user } = useAuth();

  const openCount = cases.filter((c) => c.status === 'Open').length;
  const inProgressCount = cases.filter((c) => c.status === 'In Progress').length;
  const closedCount = cases.filter((c) => c.status === 'Closed').length;

  const upcomingHearings = cases
    .flatMap((c) => c.hearings.map((h) => ({ ...h, caseId: c.id, caseTitle: c.title })))
    .filter((h) => new Date(h.date) >= new Date(new Date().toDateString()))
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(0, 5);

  const recentCases = [...cases]
    .sort((a, b) => b.openedOn.localeCompare(a.openedOn))
    .slice(0, 5);

  const firstName = user?.name.split(' ')[0] ?? 'there';

  return (
    <>
      <PageHeader
        title={`Welcome back, ${firstName}`}
        description="Here's an overview of your practice activity."
        actions={
          <Link to="/app/cases/new">
            <Button>
              <Plus className="h-4 w-4" />
              New Case
            </Button>
          </Link>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total Cases" value={cases.length} icon={FolderKanban} hint="All matters on file" />
        <StatCard label="Open" value={openCount} icon={Activity} hint="Awaiting first action" />
        <StatCard label="In Progress" value={inProgressCount} icon={CalendarClock} hint="Actively worked" />
        <StatCard label="Closed" value={closedCount} icon={CheckCircle2} hint="Resolved matters" />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader
            title="Recent Cases"
            action={
              <Link
                to="/app/cases"
                className="inline-flex items-center gap-1 text-xs font-medium text-brand-600 hover:text-brand-800"
              >
                View all <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            }
          />
          <div className="divide-y divide-brand-100">
            {recentCases.map((c) => (
              <Link
                key={c.id}
                to={`/app/cases/${c.id}`}
                className="flex items-center justify-between gap-4 px-5 py-3.5 transition hover:bg-brand-50/60"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-brand-900">{c.title}</p>
                  <p className="mt-0.5 text-xs text-brand-500">
                    {c.caseNumber} · {c.clientName}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <PriorityBadge priority={c.priority} />
                  <StatusBadge status={c.status} />
                </div>
              </Link>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader title="Upcoming Hearings" />
          <CardBody className="p-0">
            {upcomingHearings.length === 0 ? (
              <p className="px-5 py-6 text-sm text-brand-500">No hearings scheduled.</p>
            ) : (
              <ul className="divide-y divide-brand-100">
                {upcomingHearings.map((h) => (
                  <li key={h.id} className="px-5 py-3.5">
                    <Link to={`/app/cases/${h.caseId}`} className="group block">
                      <p className="text-sm font-medium text-brand-900 group-hover:text-brand-700">
                        {h.purpose}
                      </p>
                      <p className="mt-0.5 truncate text-xs text-brand-500">{h.caseTitle}</p>
                      <p className="mt-1 text-xs font-medium text-accent-600">
                        {formatDate(h.date)} · {h.time} · {h.court}
                      </p>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
      </div>
    </>
  );
}
