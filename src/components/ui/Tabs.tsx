import type { LucideIcon } from 'lucide-react';

export interface TabItem<K extends string> {
  key: K;
  label: string;
  icon: LucideIcon;
  /** Small count or tag shown after the label. */
  meta?: string | number;
}

interface TabsProps<K extends string> {
  items: TabItem<K>[];
  active: K;
  onChange: (key: K) => void;
}

export function Tabs<K extends string>({ items, active, onChange }: TabsProps<K>) {
  return (
    <div className="overflow-x-auto border-b border-brand-100" role="tablist">
      <div className="flex min-w-max gap-1">
        {items.map(({ key, label, icon: Icon, meta }) => {
          const selected = key === active;
          return (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => onChange(key)}
              className={`-mb-px inline-flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition ${
                selected
                  ? 'border-brand-800 text-brand-900'
                  : 'border-transparent text-brand-500 hover:border-brand-200 hover:text-brand-800'
              }`}
            >
              <Icon className="h-4 w-4" strokeWidth={1.75} />
              {label}
              {meta !== undefined && (
                <span className="rounded-full bg-brand-50 px-1.5 py-px text-[11px] font-semibold text-brand-500">
                  {meta}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
