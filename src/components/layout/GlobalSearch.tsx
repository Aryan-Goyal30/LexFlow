import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileText, FolderKanban, Loader2, Search, Users, type LucideIcon } from 'lucide-react';
import { QUICK_SEARCH_MIN, useGlobalSearch } from '../../hooks/useGlobalSearch';
import { errorMessage } from '../../services/api/client';
import type { GlobalSearchResult } from '../../types';

interface Option {
  key: string;
  group: 'Cases' | 'Clients' | 'Documents';
  icon: LucideIcon;
  label: string;
  detail: string;
  to: string;
}

function optionsOf(result: GlobalSearchResult): Option[] {
  return [
    ...result.cases.map((c): Option => ({
      key: `case-${c.id}`,
      group: 'Cases',
      icon: FolderKanban,
      label: `${c.caseNumber} · ${c.title}`,
      detail: c.archived ? `${c.clientName} · Archived` : c.clientName,
      to: `/app/cases/${c.id}`,
    })),
    ...result.clients.map((c): Option => ({
      key: `client-${c.id}`,
      group: 'Clients',
      icon: Users,
      label: c.name,
      detail: c.company ?? 'Client',
      to: `/app/clients/${c.id}`,
    })),
    ...result.documents.map((d): Option => ({
      key: `document-${d.id}`,
      group: 'Documents',
      icon: FileText,
      label: d.name,
      detail: `${d.caseNumber} · ${d.caseTitle}`,
      to: `/app/cases/${d.caseId}?tab=documents`,
    })),
  ];
}

/**
 * The top bar's search: matching cases, clients and documents in a dropdown as
 * you type (debounced; the server searches and applies the usual visibility).
 * Arrow keys move through the results, Enter opens one, Escape closes.
 */
export function GlobalSearch() {
  const navigate = useNavigate();
  const [text, setText] = useState('');
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const box = useRef<HTMLDivElement>(null);
  const listId = useId();
  const { query, q } = useGlobalSearch(text);

  const typed = text.trim();
  const tooShort = typed.length < QUICK_SEARCH_MIN;
  const current = !tooShort && q === typed;
  const options = current && query.data ? optionsOf(query.data) : [];
  const searching = !tooShort && (!current || query.isFetching);

  useEffect(() => setActive(0), [q]);

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [open]);

  const go = (option: Option) => {
    setOpen(false);
    setText('');
    navigate(option.to);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Escape') {
      setOpen(false);
      return;
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      setOpen(true);
      if (options.length === 0) return;
      const step = event.key === 'ArrowDown' ? 1 : -1;
      setActive((i) => (i + step + options.length) % options.length);
      return;
    }
    if (event.key === 'Enter' && options[active]) {
      event.preventDefault();
      go(options[active]);
    }
  };

  const showPanel = open && typed.length > 0;
  const optionId = (i: number) => `${listId}-option-${i}`;

  return (
    <div ref={box} className="relative min-w-0 max-w-md flex-1">
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-brand-400" />
      <input
        type="search"
        role="combobox"
        aria-label="Search cases, clients and documents"
        aria-expanded={showPanel}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={showPanel && options[active] ? optionId(active) : undefined}
        placeholder="Search cases, clients, documents…"
        value={text}
        onChange={(event) => {
          setText(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        className="w-full rounded-md border border-brand-200 bg-brand-50/60 py-2 pl-9 pr-9 text-sm placeholder:text-brand-400 focus:border-brand-500 focus:bg-white focus:ring-2 focus:ring-brand-500/20"
      />
      {searching && (
        <Loader2
          className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-brand-400"
          aria-hidden="true"
        />
      )}

      {showPanel && (
        <div className="absolute left-0 right-0 top-full z-30 mt-1.5 max-h-[24rem] overflow-y-auto rounded-lg border border-brand-100 bg-white py-1 shadow-lg">
          {tooShort ? (
            <p className="px-3 py-2 text-xs text-brand-500">
              Type at least {QUICK_SEARCH_MIN} characters to search.
            </p>
          ) : query.isError && current ? (
            <div role="alert" className="space-y-1 px-3 py-2 text-xs text-red-800">
              <p>The search failed: {errorMessage(query.error)}</p>
              <button
                type="button"
                className="font-medium underline underline-offset-2"
                onClick={() => void query.refetch()}
              >
                Try again
              </button>
            </div>
          ) : !current || (query.isPending && !query.data) ? (
            <p role="status" className="px-3 py-2 text-xs text-brand-500">
              Searching…
            </p>
          ) : options.length === 0 ? (
            <p role="status" className="px-3 py-2 text-xs text-brand-500">
              No cases, clients or documents match “{typed}”.
            </p>
          ) : null}

          <ul id={listId} role="listbox" aria-label="Search results">
            {options.map((option, i) => {
              const Icon = option.icon;
              const first = i === 0 || options[i - 1].group !== option.group;
              return (
                <li key={option.key} role="presentation">
                  {first && (
                    <p
                      role="presentation"
                      className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-brand-400"
                    >
                      {option.group}
                    </p>
                  )}
                  <div
                    id={optionId(i)}
                    role="option"
                    aria-selected={i === active}
                    tabIndex={-1}
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => go(option)}
                    onMouseEnter={() => setActive(i)}
                    className={`flex cursor-pointer items-start gap-2.5 px-3 py-2 ${i === active ? 'bg-brand-50' : ''}`}
                  >
                    <Icon className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" aria-hidden="true" />
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium text-brand-900">
                        {option.label}
                      </span>
                      <span className="block truncate text-xs text-brand-500">{option.detail}</span>
                    </span>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
