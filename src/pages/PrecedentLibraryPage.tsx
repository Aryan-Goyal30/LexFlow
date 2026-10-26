import { useId, useState, type FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { JudgmentSearchMode } from '../types';
import type { JudgmentFilters, JudgmentOrigin, JudgmentQuery } from '../services/api/lexflow';
import { useJudgmentFacets, useJudgmentList } from '../hooks/useJudgments';
import { PageHeader } from '../components/ui/PageHeader';
import { Card, CardBody } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { ErrorState, LoadingState } from '../components/ui/QueryState';
import {
  EmptyCollection,
  JudgmentCard,
  JudgmentResults,
  JudgmentSearchForm,
  Pager,
} from '../components/research/Judgments';

const MODES: readonly string[] = ['keyword', 'semantic', 'hybrid'];

function positive(raw: string | null, fallback = 1): number {
  const n = Number(raw);
  return Number.isInteger(n) && n >= 1 ? n : fallback;
}

function year(raw: string | null): number | undefined {
  const n = Number(raw);
  return raw && Number.isInteger(n) && n >= 1800 && n <= 2100 ? n : undefined;
}

/**
 * The Precedent Library: the firm's judgment collection, browsed newest
 * first or searched. Everything is in the URL (query, mode, filters, page),
 * so Back works and a search can be shared with a colleague.
 */
export function PrecedentLibraryPage() {
  const [params, setParams] = useSearchParams();
  const facets = useJudgmentFacets();

  const q = (params.get('q') ?? '').trim();
  const modeRaw = params.get('mode') ?? 'keyword';
  const mode = (MODES.includes(modeRaw) ? modeRaw : 'keyword') as JudgmentSearchMode;
  const page = positive(params.get('page'));
  const filters: JudgmentFilters = {
    court: params.get('court') || undefined,
    yearFrom: year(params.get('yearFrom')),
    yearTo: year(params.get('yearTo')),
    origin: origin(params.get('origin')),
  };
  const query: JudgmentQuery | null = q ? { q, mode, page, ...filters } : null;
  const list = useJudgmentList(filters, page, query === null);

  const update = (changes: Record<string, string | undefined>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    setParams(next);
  };

  const header = (
    <PageHeader
      title="Precedent Library"
      description="The firm's collection of judgments. Search by keywords (or by meaning, when enabled) and read each judgment with its source."
    />
  );

  if (facets.isPending) {
    return (
      <>
        {header}
        <Card>
          <LoadingState label="Loading the collection…" />
        </Card>
      </>
    );
  }
  if (facets.isError) {
    return (
      <>
        {header}
        <Card>
          <ErrorState
            title="Couldn't load the collection"
            error={facets.error}
            onRetry={() => void facets.refetch()}
          />
        </Card>
      </>
    );
  }
  const f = facets.data;
  if (f.total === 0) {
    return (
      <>
        {header}
        <EmptyCollection />
      </>
    );
  }

  return (
    <>
      {header}
      {f.synthetic > 0 && (
        <p
          role="note"
          className="mb-4 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800 ring-1 ring-inset ring-amber-600/20"
        >
          {f.synthetic === f.total
            ? 'Every judgment here is'
            : `${f.synthetic} of ${f.total} judgments ${f.synthetic === 1 ? 'is' : 'are'}`}{' '}
          synthetic test data: invented, not real judgments, never to be cited.
        </p>
      )}
      <Card className="mb-4">
        <CardBody className="space-y-4">
          <JudgmentSearchForm
            submitted={query ? { q: query.q, mode: query.mode } : null}
            facets={f}
            onSubmit={(nextQ, nextMode) => update({ q: nextQ, mode: nextMode, page: undefined })}
          />
          <FilterForm
            key={params.toString()}
            initial={filters}
            courts={f.courts}
            yearMin={f.yearMin}
            yearMax={f.yearMax}
            showOrigin={f.synthetic > 0 && f.synthetic < f.total}
            canClear={Boolean(
              filters.court || filters.yearFrom || filters.yearTo || filters.origin || q,
            )}
            onApply={(next) =>
              update({
                court: next.court,
                yearFrom: next.yearFrom?.toString(),
                yearTo: next.yearTo?.toString(),
                origin: next.origin,
                page: undefined,
              })
            }
            onClear={() => setParams(new URLSearchParams())}
          />
        </CardBody>
      </Card>

      {query ? (
        <JudgmentResults query={query} onPage={(p) => update({ page: String(p) })} />
      ) : list.isPending ? (
        <Card>
          <LoadingState label="Loading judgments…" />
        </Card>
      ) : list.isError ? (
        <Card>
          <ErrorState
            title="Couldn't load judgments"
            error={list.error}
            onRetry={() => void list.refetch()}
          />
        </Card>
      ) : (
        <section aria-label="Judgments" className="space-y-3">
          <p role="status" className="text-sm text-brand-600">
            {list.data.total === 0
              ? 'No judgments match these filters.'
              : `${list.data.total} judgment${list.data.total === 1 ? '' : 's'}, newest first.`}
          </p>
          {list.data.items.map((judgment) => (
            <JudgmentCard key={judgment.id} judgment={judgment} />
          ))}
          {list.data.total > list.data.pageSize && (
            <Pager
              page={list.data.page}
              pages={Math.ceil(list.data.total / list.data.pageSize)}
              onPage={(p) => update({ page: String(p) })}
              label="Library pages"
            />
          )}
        </section>
      )}
    </>
  );
}

function origin(raw: string | null): JudgmentOrigin | undefined {
  return raw === 'genuine' || raw === 'synthetic' ? raw : undefined;
}

/** Court, year and origin filters; reset from the address whenever it changes (key). */
function FilterForm({
  initial,
  courts,
  yearMin,
  yearMax,
  showOrigin,
  canClear,
  onApply,
  onClear,
}: {
  initial: JudgmentFilters;
  courts: string[];
  yearMin: number | null;
  yearMax: number | null;
  showOrigin: boolean;
  canClear: boolean;
  onApply: (filters: JudgmentFilters) => void;
  onClear: () => void;
}) {
  const [court, setCourt] = useState(initial.court ?? '');
  const [from, setFrom] = useState(initial.yearFrom?.toString() ?? '');
  const [to, setTo] = useState(initial.yearTo?.toString() ?? '');
  const [kind, setKind] = useState(initial.origin ?? '');
  const courtId = useId();
  const originId = useId();
  const fromId = useId();
  const toId = useId();

  const submit = (e: FormEvent) => {
    e.preventDefault();
    onApply({
      court: court || undefined,
      yearFrom: year(from),
      yearTo: year(to),
      origin: origin(kind),
    });
  };

  return (
    <form
      onSubmit={submit}
      aria-label="Filter the collection"
      className="flex flex-wrap items-end gap-3"
    >
      <div>
        <label htmlFor={courtId} className="label-text">
          Court
        </label>
        <select
          id={courtId}
          value={court}
          onChange={(e) => setCourt(e.target.value)}
          className="input-field"
        >
          <option value="">All courts</option>
          {courts.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor={fromId} className="label-text">
          From year
        </label>
        <input
          id={fromId}
          type="number"
          min={1800}
          max={2100}
          value={from}
          onChange={(e) => setFrom(e.target.value)}
          placeholder={yearMin ? String(yearMin) : undefined}
          className="input-field w-28"
        />
      </div>
      <div>
        <label htmlFor={toId} className="label-text">
          To year
        </label>
        <input
          id={toId}
          type="number"
          min={1800}
          max={2100}
          value={to}
          onChange={(e) => setTo(e.target.value)}
          placeholder={yearMax ? String(yearMax) : undefined}
          className="input-field w-28"
        />
      </div>
      {(showOrigin || initial.origin) && (
        <div>
          <label htmlFor={originId} className="label-text">
            Origin
          </label>
          <select
            id={originId}
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            className="input-field"
          >
            <option value="">Genuine and synthetic</option>
            <option value="genuine">Genuine judgments only</option>
            <option value="synthetic">Synthetic test data only</option>
          </select>
        </div>
      )}
      <Button type="submit" variant="secondary">
        Apply filters
      </Button>
      {canClear && (
        <Button type="button" variant="ghost" onClick={onClear}>
          Clear
        </Button>
      )}
    </form>
  );
}
