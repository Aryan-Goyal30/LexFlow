import { useRef, type KeyboardEvent } from 'react';
import type { LucideIcon } from 'lucide-react';
import { tabId, tabPanelId } from './tabIds';

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
  /** Base for element ids; the panel uses tabPanelId(idBase). */
  idBase: string;
  label: string;
}

/**
 * Tabs with manual activation: arrow keys, Home and End move focus between
 * tabs; Enter, Space or a click selects one. Selecting is deliberate because
 * each selection adds a browser history entry.
 */
export function Tabs<K extends string>({ items, active, onChange, idBase, label }: TabsProps<K>) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const count = items.length;
    const targets: Record<string, number> = {
      ArrowRight: (index + 1) % count,
      ArrowLeft: (index - 1 + count) % count,
      Home: 0,
      End: count - 1,
    };
    const target = targets[event.key];
    if (target === undefined) return;
    event.preventDefault();
    refs.current[target]?.focus();
  };

  return (
    <div className="overflow-x-auto border-b border-brand-100">
      <div className="flex min-w-max gap-1" role="tablist" aria-label={label}>
        {items.map(({ key, label: tabLabel, icon: Icon, meta }, index) => {
          const selected = key === active;
          return (
            <button
              key={key}
              ref={(el) => {
                refs.current[index] = el;
              }}
              id={tabId(idBase, key)}
              type="button"
              role="tab"
              aria-selected={selected}
              aria-controls={tabPanelId(idBase)}
              tabIndex={selected ? 0 : -1}
              onClick={() => onChange(key)}
              onKeyDown={(event) => handleKeyDown(event, index)}
              className={`-mb-px inline-flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-500 ${
                selected
                  ? 'border-brand-800 text-brand-900'
                  : 'border-transparent text-brand-500 hover:border-brand-200 hover:text-brand-800'
              }`}
            >
              <Icon className="h-4 w-4" strokeWidth={1.75} aria-hidden="true" />
              {tabLabel}
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
