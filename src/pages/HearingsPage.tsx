import { useId, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { CalendarClock, Clock } from 'lucide-react';
import { useHearingSchedule } from '../hooks/useCases';
import { useAuth } from '../context/AuthContext';
import { casePath } from '../lib/paths';
import { formatDate, todayIsoDate } from '../lib/format';
import type { HearingRange, ScheduledHearing } from '../types';
import { PageHeader } from '../components/ui/PageHeader';
import { Card } from '../components/ui/Card';
import { ErrorState, LoadingState, StaleDataNotice } from '../components/ui/QueryState';

function shift(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + days);
  return todayIsoDate(d);
}

const PRESETS = [
  { key: 'week', label: 'Next 7 days', range: (t: string) => [t, shift(t, 7)] },
  { key: 'month', label: 'Next 30 days', range: (t: string) => [t, shift(t, 30)] },
  { key: 'past', label: 'Past 30 days', range: (t: string) => [shift(t, -30), shift(t, -1)] },
] as const;

/**
 * Every hearing on the cases you may see, in a date range, grouped by day.
 * Archived cases are left out; cancelled hearings only when asked for.
 */
export function HearingsPage() {
  const { user } = useAuth();
  const today = todayIsoDate();
  const [range, setRange] = useState<HearingRange>({
    from: today,
    to: shift(today, 30),
    includeCancelled: false,
  });
  const fromId = useId();
  const toId = useId();
  const cancelledId = useId();
  const rangeError =
    range.to < range.from ? 'The end date must be on or after the start date.' : null;
  const schedule = useHearingSchedule(range, {
    enabled: !rangeError && !!range.from && !!range.to,
  });

  const days = useMemo(() => {
    const byDay = new Map<string, ScheduledHearing[]>();
    for (const h of schedule.data?.hearings ?? []) {
      byDay.set(h.date, [...(byDay.get(h.date) ?? []), h]);
    }
    return [...byDay];
  }, [schedule.data]);

  const scope =
    user?.role === 'Administrator'
      ? 'Hearings on every active case.'
      : 'Hearings on the cases you work on.';

  return (
    <>
      <PageHeader title="Hearings" description={scope} />

      <Card className="mb-4 p-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Period">
            {PRESETS.map((p) => {
              const [from, to] = p.range(today);
              const active = range.from === from && range.to === to;
              return (
                <button
                  key={p.key}
                  type="button"
                  aria-pressed={active}
                  onClick={() => setRange((r) => ({ ...r, from, to }))}
                  className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                    active
                      ? 'bg-brand-800 text-white'
                      : 'bg-brand-50 text-brand-600 hover:bg-brand-100'
                  }`}
                >
                  {p.label}
                </button>
              );
            })}
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label htmlFor={fromId} className="label-text">
                From
              </label>
              <input
                id={fromId}
                type="date"
                className="input-field"
                value={range.from}
                onChange={(e) => setRange((r) => ({ ...r, from: e.target.value }))}
              />
            </div>
            <div>
              <label htmlFor={toId} className="label-text">
                To
              </label>
              <input
                id={toId}
                type="date"
                className="input-field"
                value={range.to}
                aria-invalid={rangeError ? true : undefined}
                aria-describedby={rangeError ? `${toId}-error` : undefined}
                onChange={(e) => setRange((r) => ({ ...r, to: e.target.value }))}
              />
            </div>
            <label
              htmlFor={cancelledId}
              className="mb-2 inline-flex items-center gap-2 text-sm text-brand-700"
            >
              <input
                id={cancelledId}
                type="checkbox"
                className="h-4 w-4 rounded border-brand-300"
                checked={range.includeCancelled}
                onChange={(e) => setRange((r) => ({ ...r, includeCancelled: e.target.checked }))}
              />
              Show cancelled
            </label>
          </div>
        </div>
        {rangeError && (
          <p id={`${toId}-error`} role="alert" className="mt-2 text-xs text-red-600">
            {rangeError}
          </p>
        )}
      </Card>

      {schedule.isError && schedule.data && (
        <StaleDataNotice
          error={schedule.error}
          onRetry={() => schedule.refetch()}
          className="mb-4"
        />
      )}
      {rangeError ? null : schedule.isPending ? (
        <Card>
          <LoadingState label="Loading hearings…" />
        </Card>
      ) : !schedule.data ? (
        <Card>
          <ErrorState
            title="Couldn't load the hearings"
            error={schedule.error}
            onRetry={() => schedule.refetch()}
          />
        </Card>
      ) : days.length === 0 ? (
        <Card className="flex flex-col items-center px-6 py-16 text-center">
          <CalendarClock
            className="h-10 w-10 text-brand-300"
            strokeWidth={1.5}
            aria-hidden="true"
          />
          <p className="mt-3 text-sm font-medium text-brand-700">No hearings in this period</p>
        </Card>
      ) : (
        <div className="space-y-4">
          {schedule.data.truncated && (
            <p role="status" className="text-sm text-amber-800">
              Showing the first {schedule.data.hearings.length} hearings. Choose a shorter period to
              see the rest.
            </p>
          )}
          {days.map(([day, hearings]) => (
            <Card key={day} className="overflow-hidden">
              <h2 className="border-b border-brand-100 bg-brand-50/60 px-5 py-2.5 text-sm font-semibold text-brand-800">
                {formatDate(day)}
                {day === today && (
                  <span className="ml-2 text-xs font-medium text-accent-600">Today</span>
                )}
              </h2>
              <ul
                className="divide-y divide-brand-100"
                aria-label={`Hearings on ${formatDate(day)}`}
              >
                {hearings.map((h) => {
                  const cancelled = h.status === 'Cancelled';
                  return (
                    <li key={h.id} className="flex flex-col gap-1 px-5 py-3 sm:flex-row sm:gap-4">
                      <span className="flex w-28 shrink-0 items-center gap-1.5 text-sm text-brand-600">
                        <Clock className="h-3.5 w-3.5" aria-hidden="true" />
                        {h.time ?? 'Time to be confirmed'}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p
                          className={`text-sm font-medium ${
                            cancelled ? 'text-brand-500 line-through' : 'text-brand-900'
                          }`}
                        >
                          {h.purpose}
                        </p>
                        <p className="text-xs text-brand-500">
                          <Link
                            to={casePath(h.caseId)}
                            className="font-medium text-brand-700 hover:underline"
                          >
                            {h.caseTitle}
                          </Link>{' '}
                          · {h.caseNumber} · {h.court} · {h.leadAttorney}
                        </p>
                        {cancelled && (
                          <p className="text-xs font-medium text-red-700">
                            Cancelled
                            {h.cancellationReason && (
                              <span className="font-normal text-brand-600">
                                {' '}
                                · {h.cancellationReason}
                              </span>
                            )}
                          </p>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
