import { useEffect, useId, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { ChevronLeft, ChevronRight, ExternalLink, FileText, Loader2, Search } from 'lucide-react';
import type { JudgmentFacets, JudgmentHit, JudgmentSearchMode, JudgmentSummary } from '../../types';
import type { JudgmentQuery } from '../../services/api/lexflow';
import { useJudgmentSearch } from '../../hooks/useJudgments';
import { judgmentPath } from '../../lib/paths';
import { judgmentLine, QUERY_MAX } from '../../lib/judgments';
import { Button } from '../ui/Button';
import { ErrorState } from '../ui/QueryState';

const MODE_LABELS: Record<JudgmentSearchMode, string> = {
  keyword: 'Keywords',
  semantic: 'Meaning (semantic)',
  hybrid: 'Keywords and meaning (hybrid)',
};

/** Invented test data is labelled wherever it appears; it is never a real judgment. */
export function SyntheticBadge() {
  return (
    <span
      className="inline-flex items-center rounded px-1.5 py-px text-[10px] font-semibold uppercase tracking-wide text-amber-700 ring-1 ring-inset ring-amber-600/40"
      title="Invented test data: not a real judgment, never to be cited"
    >
      Synthetic test data
    </span>
  );
}

/** A judgment from a real source: genuine text, still to be checked before it is relied on. */
export function GenuineBadge() {
  return (
    <span
      className="inline-flex items-center rounded px-1.5 py-px text-[10px] font-semibold uppercase tracking-wide text-emerald-700 ring-1 ring-inset ring-emerald-600/40"
      title="From a real source whose terms were recorded at import. Check the official copy before relying on it."
    >
      Genuine judgment
    </span>
  );
}

/** A link to the judgment at its source: https only, opened without access to this page. */
export function SourceLink({ url, name }: { url: string; name: string }) {
  if (!url.startsWith('https://')) return null;
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-xs font-medium text-brand-600 underline-offset-2 hover:underline"
    >
      <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
      View at source ({name})
    </a>
  );
}

export function JudgmentCard({
  judgment: j,
  hit,
}: {
  judgment: JudgmentSummary;
  hit?: JudgmentHit;
}) {
  const passage = hit?.passage;
  return (
    <article className="rounded-lg border border-brand-100 bg-white p-4" aria-label={j.title}>
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold text-brand-900">
          <Link
            to={judgmentPath(j.id, passage?.sectionNumber ?? 1)}
            className="rounded underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          >
            {j.title}
          </Link>
        </h3>
        {j.synthetic ? <SyntheticBadge /> : <GenuineBadge />}
      </div>
      <p className="mt-1 text-xs text-brand-500">{judgmentLine(j)}</p>
      {passage && (
        <blockquote className="mt-3 border-l-2 border-accent-500/60 pl-3 text-sm leading-relaxed text-brand-800">
          <p className="whitespace-pre-wrap break-words">{passage.text}</p>
          <footer className="mt-1 text-xs text-brand-500">
            {passage.pageNumber ? `Page ${passage.pageNumber}` : `Part ${passage.sectionNumber}`}
          </footer>
        </blockquote>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-4">
        <Link
          to={judgmentPath(j.id, passage?.sectionNumber ?? 1)}
          className="inline-flex items-center gap-1 text-xs font-medium text-brand-700 underline-offset-2 hover:underline"
          aria-label={`Read ${j.title}`}
        >
          <FileText className="h-3.5 w-3.5" aria-hidden="true" />
          Read the judgment
        </Link>
        <SourceLink url={j.sourceUrl} name={j.sourceName} />
      </div>
    </article>
  );
}

/**
 * The search box. Semantic and hybrid modes are offered only when the server
 * says they work; otherwise they are disabled and the reason is shown.
 */
export function JudgmentSearchForm({
  submitted,
  facets,
  onSubmit,
  label = 'Search the judgment collection',
}: {
  submitted: { q: string; mode: JudgmentSearchMode } | null;
  facets: JudgmentFacets | undefined;
  onSubmit: (q: string, mode: JudgmentSearchMode) => void;
  label?: string;
}) {
  const [draft, setDraft] = useState(submitted?.q ?? '');
  const [mode, setMode] = useState<JudgmentSearchMode>(submitted?.mode ?? 'keyword');
  const [problem, setProblem] = useState<string | null>(null);
  const inputId = useId();
  const modeId = useId();
  const problemId = useId();
  const modes = facets?.modes;
  const available = (m: JudgmentSearchMode) => m === 'keyword' || Boolean(modes?.[m]);

  useEffect(() => {
    if (submitted) {
      setDraft(submitted.q);
      setMode(submitted.mode);
    }
  }, [submitted]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const q = draft.trim();
    if (!q) {
      setProblem('Type something to search for.');
      return;
    }
    if (q.length > QUERY_MAX) {
      setProblem(`Use at most ${QUERY_MAX} characters.`);
      return;
    }
    setProblem(null);
    onSubmit(q, available(mode) ? mode : 'keyword');
  };

  return (
    <form onSubmit={submit} role="search" aria-label={label} className="space-y-2" noValidate>
      <div className="flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <label htmlFor={inputId} className="sr-only">
            {label}
          </label>
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-brand-400"
            aria-hidden="true"
          />
          <input
            id={inputId}
            type="search"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="e.g. deceptively similar trade mark, notice to quit"
            className="input-field pl-9"
            maxLength={QUERY_MAX + 1}
            aria-invalid={problem ? true : undefined}
            aria-describedby={problem ? problemId : undefined}
          />
        </div>
        <label htmlFor={modeId} className="sr-only">
          Search by
        </label>
        <select
          id={modeId}
          value={mode}
          onChange={(e) => setMode(e.target.value as JudgmentSearchMode)}
          className="input-field sm:w-64"
        >
          {(Object.keys(MODE_LABELS) as JudgmentSearchMode[]).map((m) => (
            <option key={m} value={m} disabled={!available(m)}>
              {MODE_LABELS[m]}
              {available(m) ? '' : ' (unavailable)'}
            </option>
          ))}
        </select>
        <Button type="submit">Search</Button>
      </div>
      {problem && (
        <p id={problemId} role="alert" className="text-sm text-red-700">
          {problem}
        </p>
      )}
      {modes && !modes.semantic && (
        <p className="text-xs text-brand-500">
          Searching by meaning is unavailable: {modes.unavailableReason ?? 'not configured.'}{' '}
          Keyword search works.
        </p>
      )}
    </form>
  );
}

/** Results of one submitted search, paged. Stale results are never shown. */
export function JudgmentResults({
  query,
  onPage,
}: {
  query: JudgmentQuery;
  onPage: (page: number) => void;
}) {
  const result = useJudgmentSearch(query);
  if (result.isPending) {
    return (
      <div className="flex items-center gap-2 py-6 text-sm text-brand-600" role="status">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        Searching for “{query.q}”…
      </div>
    );
  }
  if (result.isError) {
    return (
      <ErrorState
        title="The search did not work"
        error={result.error}
        onRetry={() => void result.refetch()}
      />
    );
  }
  const body = result.data;
  const pages = Math.max(1, Math.ceil(body.total / body.pageSize));
  return (
    <section aria-label="Search results" className="space-y-3">
      <p role="status" className="text-sm text-brand-600">
        {body.total === 0
          ? `No judgments matched “${query.q}”.`
          : `${body.total} judgment${body.total === 1 ? '' : 's'} matched “${query.q}”` +
            (body.total >= body.maxResults ? ` (the first ${body.maxResults} are ranked)` : '') +
            ` · ${MODE_LABELS[body.mode]}`}
      </p>
      {body.keywordMatch === 'any' && body.total > 0 && (
        <p className="text-sm text-amber-800">
          No passage contains every word of your search, so these passages contain some of the
          words. Try fewer or different words for a closer match.
        </p>
      )}
      {body.results.map((hit) => (
        <JudgmentCard key={hit.judgment.id} judgment={hit.judgment} hit={hit} />
      ))}
      {body.total > body.pageSize && (
        <Pager page={body.page} pages={pages} onPage={onPage} label="Search result pages" />
      )}
    </section>
  );
}

export function Pager({
  page,
  pages,
  onPage,
  label,
}: {
  page: number;
  pages: number;
  onPage: (page: number) => void;
  label: string;
}) {
  return (
    <nav aria-label={label} className="flex items-center justify-between gap-3 pt-2">
      <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        Previous
      </Button>
      <span className="text-sm text-brand-600">
        Page {page} of {pages}
      </span>
      <Button
        variant="secondary"
        size="sm"
        disabled={page >= pages}
        onClick={() => onPage(page + 1)}
      >
        Next
        <ChevronRight className="h-4 w-4" aria-hidden="true" />
      </Button>
    </nav>
  );
}

/** Shown while the collection holds no judgments (no approved source imported yet). */
export function EmptyCollection() {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-brand-100 bg-white px-6 py-12 text-center">
      <FileText className="h-9 w-9 text-brand-300" strokeWidth={1.5} aria-hidden="true" />
      <p className="mt-3 text-sm font-medium text-brand-700">The judgment collection is empty</p>
      <p className="mt-1 max-w-md text-sm text-brand-500">
        Judgments are added by an administrator from a source whose terms of use have been checked
        (see the server guide). LexFlow does not include or download judgments by itself.
      </p>
    </div>
  );
}
