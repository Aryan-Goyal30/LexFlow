import { PlugZap, ShieldAlert } from 'lucide-react';
import type { AnalysisStatus } from '../../types/ai';

/** Shown with every AI result, and wherever AI output will appear. */
export function DecisionSupportNote() {
  return (
    <p className="flex items-start gap-2 text-xs leading-relaxed text-brand-500">
      <ShieldAlert className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <span>
        AI output in LexFlow is decision support for the advocate. It is not legal advice and does
        not replace a lawyer&apos;s judgment or a court&apos;s decision. LexFlow checks that each
        quote occurs in the source it cites; it does not check that the reading of it is legally
        right. Verify every point against its source.
      </span>
    </p>
  );
}

/** Honest state for an AI feature that cannot run on this server. */
export function UnavailableNotice({
  feature,
  children,
}: {
  feature: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex gap-3 rounded-lg border border-dashed border-brand-200 bg-brand-50/60 p-4">
      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-white text-brand-500 ring-1 ring-brand-100">
        <PlugZap className="h-4 w-4" aria-hidden="true" />
      </span>
      <div className="text-sm">
        <p className="font-medium text-brand-900">{feature} is not available</p>
        <div className="mt-1 leading-relaxed text-brand-600">{children}</div>
      </div>
    </div>
  );
}

export type AiPillStatus = AnalysisStatus | 'unavailable' | 'idle';

const statusStyles: Record<AiPillStatus, { label: string; className: string }> = {
  unavailable: {
    label: 'Not available',
    className: 'bg-brand-100 text-brand-600 ring-brand-600/20',
  },
  idle: { label: 'Ready to run', className: 'bg-sky-50 text-sky-700 ring-sky-600/20' },
  queued: { label: 'Waiting…', className: 'bg-amber-50 text-amber-700 ring-amber-600/20' },
  running: { label: 'Running…', className: 'bg-amber-50 text-amber-700 ring-amber-600/20' },
  ready: { label: 'Complete', className: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20' },
  failed: { label: 'Failed', className: 'bg-red-50 text-red-700 ring-red-600/20' },
};

export function AiStatusPill({ status }: { status: AiPillStatus }) {
  const { label, className } = statusStyles[status];
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${className}`}
    >
      {label}
    </span>
  );
}
