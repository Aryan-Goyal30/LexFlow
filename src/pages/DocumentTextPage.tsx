import { useId } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ArrowLeft, ChevronLeft, ChevronRight, FileText } from 'lucide-react';
import { useDocumentText } from '../hooks/useCases';
import { ApiError } from '../services/api/client';
import { casePath, documentTextPath } from '../lib/paths';
import { formatDate } from '../lib/format';
import { Card, CardBody } from '../components/ui/Card';
import { ErrorState, LoadingState } from '../components/ui/QueryState';

function sectionFrom(raw: string | null): number {
  const value = Number(raw ?? '1');
  return Number.isInteger(value) && value >= 1 ? value : 1;
}

/**
 * The text the server extracted from a stored document, one page (PDF) or
 * part (Word, text) at a time. Shown exactly as extracted; nothing is added.
 */
export function DocumentTextPage() {
  const { caseId = '', documentId = '' } = useParams<{ caseId: string; documentId: string }>();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const section = sectionFrom(params.get('section'));
  const query = useDocumentText(documentId, section);
  const jumpId = useId();

  const back = (
    <Link
      to={`${casePath(caseId)}?tab=documents`}
      className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-brand-600 hover:text-brand-800"
    >
      <ArrowLeft className="h-4 w-4" aria-hidden="true" />
      Back to the documents
    </Link>
  );

  if (query.isPending) {
    return (
      <>
        {back}
        <Card>
          <LoadingState label="Loading the text…" />
        </Card>
      </>
    );
  }
  if (!query.data) {
    const error = query.error;
    const title =
      error instanceof ApiError && error.isNotFound
        ? 'Not found'
        : error instanceof ApiError && error.code === 'text-not-available'
          ? 'The text is not available'
          : "Couldn't load the text";
    return (
      <>
        {back}
        <Card>
          <ErrorState
            title={title}
            error={error}
            onRetry={
              error instanceof ApiError && error.status < 500 ? undefined : () => query.refetch()
            }
          />
        </Card>
      </>
    );
  }

  const t = query.data;
  const paginated = t.pageCount !== null;
  const unit = paginated ? 'Page' : 'Part';
  const label = `${unit} ${t.section.number} of ${t.sectionCount}`;
  const go = (n: number) => navigate(documentTextPath(caseId, documentId, n));

  return (
    <>
      {back}
      <header className="mb-4">
        <h1 className="flex items-center gap-2 text-xl font-bold text-brand-900">
          <FileText className="h-5 w-5 text-brand-400" aria-hidden="true" />
          {t.documentName}
        </h1>
        <p className="mt-1 text-sm text-brand-500">
          Extracted text · {label}
          {!paginated &&
            ' · Word and text files have no fixed pages, so their text is shown in parts.'}
        </p>
      </header>

      <nav
        aria-label={`${unit}s`}
        className="mb-3 flex flex-wrap items-center justify-between gap-3"
      >
        <div className="flex gap-2">
          {t.section.number > 1 ? (
            <Link
              to={documentTextPath(caseId, documentId, t.section.number - 1)}
              className="inline-flex items-center gap-1 rounded-md border border-brand-200 bg-white px-3 py-1.5 text-sm text-brand-800 hover:bg-brand-50"
            >
              <ChevronLeft className="h-4 w-4" aria-hidden="true" />
              Previous {unit.toLowerCase()}
            </Link>
          ) : null}
          {t.section.number < t.sectionCount ? (
            <Link
              to={documentTextPath(caseId, documentId, t.section.number + 1)}
              className="inline-flex items-center gap-1 rounded-md border border-brand-200 bg-white px-3 py-1.5 text-sm text-brand-800 hover:bg-brand-50"
            >
              Next {unit.toLowerCase()}
              <ChevronRight className="h-4 w-4" aria-hidden="true" />
            </Link>
          ) : null}
        </div>
        {t.sectionCount > 1 && (
          <div className="flex items-center gap-2">
            <label htmlFor={jumpId} className="text-sm text-brand-600">
              Go to {unit.toLowerCase()}
            </label>
            <select
              id={jumpId}
              className="input-field w-24 py-1"
              value={t.section.number}
              onChange={(e) => go(Number(e.target.value))}
            >
              {Array.from({ length: t.sectionCount }, (_, i) => i + 1).map((n) => (
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
          <article aria-label={label}>
            {t.section.text ? (
              <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-relaxed text-brand-900">
                {t.section.text}
              </pre>
            ) : (
              <p className="text-sm text-brand-500">
                No text was found on this page. It may be an image or a scanned page (OCR is not
                available).
              </p>
            )}
          </article>
        </CardBody>
      </Card>

      <p className="mt-3 text-xs text-brand-500">
        Read from the uploaded file by a program{t.extractor ? ` (${t.extractor})` : ''}
        {t.extractedAt ? ` on ${formatDate(t.extractedAt.slice(0, 10))}` : ''}. Check it against the
        original document before relying on it.
      </p>
    </>
  );
}
