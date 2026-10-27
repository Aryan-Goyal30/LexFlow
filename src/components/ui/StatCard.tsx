import type { LucideIcon } from 'lucide-react';
import { Card } from './Card';

interface StatCardProps {
  label: string;
  value: string | number;
  icon: LucideIcon;
  hint?: string;
}

export function StatCard({ label, value, icon: Icon, hint }: StatCardProps) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-brand-500">{label}</p>
          <p className="mt-2 font-sans text-3xl font-semibold tabular-nums tracking-[-0.02em] text-brand-900">
            {value}
          </p>
          {hint && <p className="mt-1 text-xs text-brand-400">{hint}</p>}
        </div>
        <span className="rounded-md p-2 text-accent-600 ring-1 ring-inset ring-brand-100">
          <Icon className="h-5 w-5" strokeWidth={1.75} />
        </span>
      </div>
    </Card>
  );
}
