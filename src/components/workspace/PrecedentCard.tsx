import { Link } from 'react-router-dom';
import { BookOpen } from 'lucide-react';
import type { AnalysisPrecedent } from '../../types/ai';
import { judgmentPath } from '../../lib/paths';
import { GenuineBadge, SyntheticBadge } from '../research/Judgments';

const place = (page: number | null, section: number) =>
  page !== null ? `page ${page}` : `part ${section}`;

/**
 * A comparison with a judgment passage retrieved for this analysis. Title,
 * court, citation and year come from the judgment collection, not from the
 * model; the link opens the passage that was compared. There is no relevance
 * percentage: the model makes no score, only the retrieval rank is shown.
 */
export function PrecedentCard({ precedent: p }: { precedent: AnalysisPrecedent }) {
  return (
    <article className="rounded-lg border border-brand-100 bg-white p-4" aria-label={p.title}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h4 className="font-sans text-sm font-semibold text-brand-900">{p.title}</h4>
          <p className="mt-0.5 text-xs text-brand-500">
            {[p.citation, p.court, p.year].filter(Boolean).join(' · ')}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {p.synthetic ? <SyntheticBadge /> : <GenuineBadge />}
          <span className="rounded-full bg-brand-50 px-2 py-0.5 text-xs text-brand-600">
            Retrieved #{p.retrievalRank}
          </span>
        </div>
      </div>
      <p className="mt-3 text-sm leading-relaxed text-brand-700">{p.summary}</p>
      {(p.similarities.length > 0 || p.differences.length > 0) && (
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <PointList title="Similar to this case" points={p.similarities} />
          <PointList title="Distinguishable on" points={p.differences} />
        </div>
      )}
      <Link
        to={judgmentPath(p.judgmentId, p.passage.sectionNumber)}
        className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-brand-700 underline-offset-2 hover:underline"
      >
        <BookOpen className="h-3.5 w-3.5" aria-hidden="true" />
        Read the passage ({place(p.passage.pageNumber, p.passage.sectionNumber)})
      </Link>
    </article>
  );
}

function PointList({ title, points }: { title: string; points: string[] }) {
  if (points.length === 0) return null;
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-brand-400">{title}</p>
      <ul className="mt-1 list-disc space-y-1 pl-4 text-sm text-brand-700">
        {points.map((point, i) => (
          <li key={`${i}-${point}`}>{point}</li>
        ))}
      </ul>
    </div>
  );
}
