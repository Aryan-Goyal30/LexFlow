import { useId } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { AlertTriangle, ArrowLeft, ChevronLeft, ChevronRight, Scale } from 'lucide-react';
import { useJudgment, useJudgmentText } from '../hooks/useJudgments';
import { ApiError } from '../services/api/client';
import { PRECEDENTS_PATH, judgmentPath } from '../lib/paths';
import { formatDate } from '../lib/format';
import { judgmentLine } from '../lib/judgments';
import { Card, CardBody } from '../components/ui/Card';
import { ErrorState, LoadingState } from '../components/ui/QueryState';
import { SourceLink, SyntheticBadge } from '../components/research/Judgments';

function sectionFrom(raw: string | null): number {
  const value = Number(raw ?? '1');
  return Number.isInteger(value) && value >= 1 ? value : 1;
}

/** One judgment: its metadata, its source and terms of use, and its text page by page. */
export function JudgmentPage() {
  const { judgmentId = '' } = useParams<{ judgmentId: string }>();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const section = sectionFrom(params.get('section'));
  const judgment = useJudgment(judgmentId);
  const text = useJudgmentText(judgmentId, section);
  const jumpId = useId();

  const back = (
    <Link
      to={PRECEDENTS_PATH}
      className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-brand-600 hover:text-brand-800"
    >
      <ArrowLeft className="h-4 w-4" aria-hidden="true" />
      Precedent Library
    </Link>
  );

  if (judgment.isPending) {
    return (
      <>
        {back}
        <Card>
          <LoadingState label="Loading the judgment…" />
        </Card>
      </>
    );
  }
  if (judgment.isError) {
    const notFound = judgment.error instanceof ApiError && judgment.error.isNotFound;
    return (
      <>
        {back}
        <Card>
          <ErrorState
            title={notFound ? 'Not found' : "Couldn't load the judgment"}
            error={judgment.error}
            onRetry={notFound ? undefined : () => void judgment.refetch()}
          />
        </Card>
      </>
    );
  }

  const j = judgment.data;
  const unit = j.pageCount !== null ? 'Page' : 'Part';

  return (
    <>
      {back}
      <header className="mb-4">
        <h1 className="flex flex-wrap items-center gap-2 text-xl font-bold text-brand-900">
          <Scale className="h-5 w-5 text-brand-400" aria-hidden="true" />
          {j.title}
          {j.synthetic && <SyntheticBadge />}
        </h1>
        <p className="mt-1 text-sm text-brand-500">{judgmentLine(j)}</p>
        {j.bench && <p className="text-sm text-brand-500">Bench: {j.bench}</p>}
        {j.practiceAreas.length > 0 && (
          <p className="text-sm text-brand-500">{j.practiceAreas.join(', ')}</p>
        )}
      </header>

      {j.synthetic && (
        <p
          role="alert"
          className="mb-4 flex items-start gap-2 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800 ring-1 ring-inset ring-amber-600/20"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          Synthetic test data: this judgment was invented for testing. It is not real and must never
          be cited.
        </p>
      )}

      <Card className="mb-4">
        <CardBody>
          <h2 className="text-sm font-semibold text-brand-900">Source</h2>
          <dl className="mt-2 grid gap-x-4 gap-y-1 text-sm sm:grid-cols-[10rem_1fr]">
            <dt className="text-brand-500">From</dt>
            <dd className="text-brand-800">{j.source.name}</dd>
            <dt className="text-brand-500">Terms of use</dt>
            <dd className="text-brand-800">
              Read on {formatDate(j.source.termsCheckedOn)} by {j.source.termsCheckedBy}
              {j.source.termsUrl.startsWith('https://') && (
                <>
                  {' · '}
                  <a
                    href={j.source.termsUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-brand-600 underline-offset-2 hover:underline"
                  >
                    the terms
                  </a>
                </>
              )}
            </dd>
            <dt className="text-brand-500">Permitted use</dt>
            <dd className="text-brand-800">{j.source.permittedUse}</dd>
            <dt className="text-brand-500">Imported</dt>
            <dd className="text-brand-800">
              {formatDate(j.importedAt.slice(0, 10))} · text read by {j.extractor}
            </dd>
          </dl>
          <div className="mt-3">
            <SourceLink url={j.sourceUrl} name={j.sourceName} />
          </div>
        </CardBody>
      </Card>

      <nav
        aria-label={`${unit}s`}
        className="mb-3 flex flex-wrap items-center justify-between gap-3"
      >
        <div className="flex gap-2">
          {section > 1 && (
            <Link
              to={judgmentPath(j.id, section - 1)}
              className="inline-flex items-center gap-1 rounded-md border border-brand-200 bg-white px-3 py-1.5 text-sm text-brand-800 hover:bg-brand-50"
            >
              <ChevronLeft className="h-4 w-4" aria-hidden="true" />
              Previous {unit.toLowerCase()}
            </Link>
          )}
          {section < j.sectionCount && (
            <Link
              to={judgmentPath(j.id, section + 1)}
              className="inline-flex items-center gap-1 rounded-md border border-brand-200 bg-white px-3 py-1.5 text-sm text-brand-800 hover:bg-brand-50"
            >
              Next {unit.toLowerCase()}
              <ChevronRight className="h-4 w-4" aria-hidden="true" />
            </Link>
          )}
        </div>
        {j.sectionCount > 1 && (
          <div className="flex items-center gap-2">
            <label htmlFor={jumpId} className="text-sm text-brand-600">
              Go to {unit.toLowerCase()}
            </label>
            <select
              id={jumpId}
              className="input-field w-24 py-1"
              value={section}
              onChange={(e) => navigate(judgmentPath(j.id, Number(e.target.value)))}
            >
              {Array.from({ length: j.sectionCount }, (_, i) => i + 1).map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </div>
        )}
      </nav>

      <Card>
        <CardBody>
          {text.isPending ? (
            <LoadingState label="Loading the text…" />
          ) : text.isError ? (
            <ErrorState title="Couldn't load this part of the text" error={text.error} />
          ) : (
            <article aria-label={`${unit} ${text.data.section.number} of ${j.sectionCount}`}>
              <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-relaxed text-brand-900">
                {text.data.section.text}
              </pre>
            </article>
          )}
        </CardBody>
      </Card>
      <p className="mt-3 text-xs text-brand-500">
        Text read from the imported file by a program. Check it against the source before relying on
        it.
      </p>
    </>
  );
}
