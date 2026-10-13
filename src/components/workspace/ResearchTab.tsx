import { useId, useState, type FormEvent } from 'react';
import { BookOpenText, Loader2, Search } from 'lucide-react';
import type { Case } from '../../types';
import type { AiAssistant } from '../../hooks/useAiAssistant';
import { Card, CardBody, CardHeader } from '../ui/Card';
import { Button } from '../ui/Button';
import { AiStatusPill, DecisionSupportNote, NotConnectedNotice } from './AiNotices';
import { PrecedentCard } from './PrecedentCard';

export function ResearchTab({ legalCase: c, ai }: { legalCase: Case; ai: AiAssistant }) {
  const [query, setQuery] = useState('');
  const inputId = useId();
  const { status, query: searchedQuery, results, error } = ai.research;
  const running = status === 'running';

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (query.trim()) void ai.searchPrecedents(query);
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Precedent Research" action={<AiStatusPill status={status} />} />
        <CardBody className="space-y-4">
          <p className="text-sm leading-relaxed text-brand-700">
            Once a collection of past judgments and a search service are connected, you will be able
            to search for precedents relevant to this {c.practiceArea.toLowerCase()} matter. Results
            will be ranked against this case's facts, with points of similarity and difference set
            out for each.
          </p>

          <form onSubmit={handleSubmit} className="flex flex-col gap-2 sm:flex-row" role="search">
            <div className="relative flex-1">
              <label htmlFor={inputId} className="sr-only">
                Search precedents
              </label>
              <Search
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-brand-400"
                aria-hidden="true"
              />
              <input
                id={inputId}
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g. interim injunction, deceptively similar trade mark"
                className="input-field pl-9"
                disabled={!ai.connected}
              />
            </div>
            <Button type="submit" disabled={!ai.connected || !query.trim() || running}>
              {running && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
              {running ? 'Searching…' : 'Search precedents'}
            </Button>
          </form>

          {!ai.connected && (
            <NotConnectedNotice feature="Precedent research">
              Searching needs a collection of past judgments and a search service. Neither is
              connected in this version of LexFlow, so no precedents are shown.
            </NotConnectedNotice>
          )}
          <DecisionSupportNote />
        </CardBody>
      </Card>

      <div aria-live="polite">
        {running && <p className="text-sm text-brand-600">Searching for “{searchedQuery}”…</p>}

        {status === 'error' && error && (
          <p
            role="alert"
            className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-inset ring-red-600/20"
          >
            {error} No results are shown.
          </p>
        )}

        {status === 'ready' && results && (
          <Card>
            <CardHeader title={`Results for “${searchedQuery}” (${results.length})`} />
            <CardBody className="space-y-3">
              {results.length === 0 ? (
                <p className="text-sm text-brand-500">No precedents matched this search.</p>
              ) : (
                results.map((p) => <PrecedentCard key={p.id} precedent={p} />)
              )}
            </CardBody>
          </Card>
        )}
      </div>

      {!running && status !== 'ready' && status !== 'error' && (
        <div className="flex flex-col items-center justify-center rounded-lg border border-brand-100 bg-white px-6 py-12 text-center">
          <BookOpenText className="h-9 w-9 text-brand-300" strokeWidth={1.5} aria-hidden="true" />
          <p className="mt-3 text-sm font-medium text-brand-700">No research yet</p>
          <p className="mt-1 max-w-sm text-sm text-brand-500">
            {ai.connected
              ? 'Search above to find precedents for this case.'
              : 'Precedent search becomes available once research is connected.'}
          </p>
        </div>
      )}
    </div>
  );
}
