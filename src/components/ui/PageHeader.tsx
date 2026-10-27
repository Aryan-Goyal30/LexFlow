import type { ReactNode } from 'react';

interface PageHeaderProps {
  title: string;
  description?: string;
  actions?: ReactNode;
}

export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <div className="mb-8 flex flex-col gap-4 border-b border-brand-100 pb-6 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-[1.75rem] font-bold leading-tight tracking-[-0.02em] text-brand-900">
          {title}
        </h1>
        {description && (
          <p className="mt-1.5 max-w-[65ch] text-sm leading-relaxed text-brand-500">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}
