import type { CasePriority, CaseStatus } from '../../types';

const statusStyles: Record<CaseStatus, string> = {
  Open: 'bg-blue-50 text-blue-700 ring-blue-600/20',
  'In Progress': 'bg-amber-50 text-amber-700 ring-amber-600/20',
  'On Hold': 'bg-brand-100 text-brand-700 ring-brand-600/20',
  Closed: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
};

const priorityStyles: Record<CasePriority, string> = {
  Low: 'bg-brand-50 text-brand-600 ring-brand-500/20',
  Medium: 'bg-sky-50 text-sky-700 ring-sky-600/20',
  High: 'bg-orange-50 text-orange-700 ring-orange-600/20',
  Critical: 'bg-red-50 text-red-700 ring-red-600/20',
};

function Pill({ text, className }: { text: string; className: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${className}`}
    >
      {text}
    </span>
  );
}

export function StatusBadge({ status }: { status: CaseStatus }) {
  return <Pill text={status} className={statusStyles[status]} />;
}

export function PriorityBadge({ priority }: { priority: CasePriority }) {
  return <Pill text={priority} className={priorityStyles[priority]} />;
}

/** Marks an archived case: kept in full, read-only, hidden from the default list. */
export function ArchivedBadge() {
  return (
    <span className="inline-flex items-center rounded-full bg-brand-100 px-2.5 py-0.5 text-xs font-medium text-brand-700 ring-1 ring-inset ring-brand-600/30">
      Archived
    </span>
  );
}

/** Marks fictional sample records so they are never mistaken for real data. */
export function SampleBadge() {
  return (
    <span
      className="inline-flex items-center rounded px-1.5 py-px text-[10px] font-semibold uppercase tracking-wide text-accent-600 ring-1 ring-inset ring-accent-500/40"
      title="Fictional sample data"
    >
      Sample
    </span>
  );
}
