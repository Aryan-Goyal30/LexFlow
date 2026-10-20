import { useState } from 'react';
import { Link } from 'react-router-dom';
import { BookOpenText } from 'lucide-react';
import type { Case } from '../../types';
import type { JudgmentQuery } from '../../services/api/lexflow';
import { useJudgmentFacets } from '../../hooks/useJudgments';
import { PRECEDENTS_PATH } from '../../lib/paths';
import { Card, CardBody, CardHeader } from '../ui/Card';
import { ErrorState, LoadingState } from '../ui/QueryState';
import { EmptyCollection, JudgmentResults, JudgmentSearchForm } from '../research/Judgments';

/**
 * Precedent research for a case: a search of the firm's judgment collection
 * (the same search as the Precedent Library). Results are passages of stored
 * judgments ranked against the words typed, not against this case's facts,
 * and nothing is generated: comparing precedents with the case is the
 * lawyer's work (AI analysis comes in a later phase).
 */
export function ResearchTab({ legalCase: c }: { legalCase: Case }) {
  const facets = useJudgmentFacets();
  const [query, setQuery] = useState<JudgmentQuery | null>(null);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Precedent Research" />
        <CardBody className="space-y-4">
          <p className="text-sm leading-relaxed text-brand-700">
            Search the firm's judgment collection for precedents relevant to this{' '}
            {c.practiceArea.toLowerCase()} matter. Each result shows the passage that matched, with
            its court, date and citation, and links to the full judgment and its source. Read the
            judgment before relying on it.
          </p>
          {facets.isPending ? (
            <LoadingState label="Loading the collection…" />
          ) : facets.isError ? (
            <ErrorState
              title="Couldn't load the collection"
              error={facets.error}
              onRetry={() => void facets.refetch()}
            />
          ) : facets.data.total === 0 ? (
            <EmptyCollection />
          ) : (
            <>
              <JudgmentSearchForm
                submitted={query ? { q: query.q, mode: query.mode } : null}
                facets={facets.data}
                onSubmit={(q, mode) => setQuery({ q, mode, page: 1 })}
                label="Search precedents"
              />
              <p className="text-xs text-brand-500">
                {facets.data.total} judgment{facets.data.total === 1 ? '' : 's'} in the collection
                {facets.data.synthetic > 0 &&
                  ` (${facets.data.synthetic} synthetic test record${facets.data.synthetic === 1 ? '' : 's'}, not real judgments)`}
                . Browse them in the{' '}
                <Link to={PRECEDENTS_PATH} className="font-medium text-brand-700 hover:underline">
                  Precedent Library
                </Link>
                .
              </p>
            </>
          )}
        </CardBody>
      </Card>

      {query ? (
        <JudgmentResults query={query} onPage={(page) => setQuery({ ...query, page })} />
      ) : (
        facets.data &&
        facets.data.total > 0 && (
          <div className="flex flex-col items-center justify-center rounded-lg border border-brand-100 bg-white px-6 py-12 text-center">
            <BookOpenText className="h-9 w-9 text-brand-300" strokeWidth={1.5} aria-hidden="true" />
            <p className="mt-3 text-sm font-medium text-brand-700">No search yet</p>
            <p className="mt-1 max-w-sm text-sm text-brand-500">
              Search above to find judgments for this case.
            </p>
          </div>
        )
      )}
    </div>
  );
}
