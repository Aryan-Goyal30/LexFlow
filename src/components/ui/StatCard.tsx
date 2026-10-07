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
          <p className="mt-2 text-3xl font-semibold text-brand-900 font-sans">{value}</p>
          {hint && <p className="mt-1 text-xs text-brand-400">{hint}</p>}
        </div>
        <span className="rounded-lg bg-brand-50 p-2.5 text-brand-700">
          <Icon className="h-5 w-5" strokeWidth={1.75} />
        </span>
      </div>
    </Card>
  );
}
