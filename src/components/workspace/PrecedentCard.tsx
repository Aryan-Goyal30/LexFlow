import type { Precedent } from '../../types/ai';

export function PrecedentCard({ precedent: p }: { precedent: Precedent }) {
  return (
    <article className="rounded-lg border border-brand-100 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h4 className="text-sm font-semibold text-brand-900 font-sans">{p.title}</h4>
          <p className="mt-0.5 text-xs text-brand-500">
            {p.citation} · {p.court} · {p.year}
          </p>
        </div>
        <span className="shrink-0 rounded-full bg-brand-50 px-2 py-0.5 text-xs font-semibold tabular-nums text-brand-700">
          {Math.round(p.relevance * 100)}% match
        </span>
      </div>
      <p className="mt-3 text-sm leading-relaxed text-brand-700">{p.summary}</p>
      {(p.similarities.length > 0 || p.differences.length > 0) && (
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <PointList title="Similar to this case" points={p.similarities} />
          <PointList title="Distinguishable on" points={p.differences} />
        </div>
      )}
    </article>
  );
}

function PointList({ title, points }: { title: string; points: string[] }) {
  if (points.length === 0) return null;
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-brand-400">{title}</p>
      <ul className="mt-1 list-disc space-y-1 pl-4 text-sm text-brand-700">
        {points.map((point) => (
          <li key={point}>{point}</li>
        ))}
      </ul>
    </div>
  );
}
