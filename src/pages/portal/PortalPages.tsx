import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, CalendarClock, Download, FileText, FolderOpen } from 'lucide-react';
import { usePortalCase, usePortalCases } from '../../hooks/useCases';
import { ApiError } from '../../services/api/client';
import { PORTAL_PATH, portalCasePath } from '../../lib/paths';
import { formatDate } from '../../lib/format';
import { Card, CardBody, CardHeader } from '../../components/ui/Card';
import { PageHeader } from '../../components/ui/PageHeader';
import { StatusBadge } from '../../components/ui/Badge';
import { ErrorState, LoadingState } from '../../components/ui/QueryState';

/** The client's cases. */
export function PortalCasesPage() {
  const cases = usePortalCases();
  return (
    <>
      <PageHeader
        title="Your Cases"
        description="Your matters with the firm, their next hearings and the documents shared with you."
      />
      {cases.isPending ? (
        <Card>
          <LoadingState label="Loading your cases…" />
        </Card>
      ) : !cases.data ? (
        <Card>
          <ErrorState
            title="Couldn't load your cases"
            error={cases.error}
            onRetry={() => cases.refetch()}
          />
        </Card>
      ) : cases.data.length === 0 ? (
        <Card className="flex flex-col items-center px-6 py-16 text-center">
          <FolderOpen className="h-10 w-10 text-brand-300" strokeWidth={1.5} aria-hidden="true" />
          <p className="mt-3 text-sm font-medium text-brand-700">No cases to show</p>
          <p className="mt-1 text-sm text-brand-500">
            Your advocate will let you know when a matter is opened.
          </p>
        </Card>
      ) : (
        <ul className="space-y-3" aria-label="Your cases">
          {cases.data.map((c) => (
            <li key={c.id}>
              <Card className="p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-semibold uppercase tracking-wide text-brand-400">
                    {c.caseNumber}
                  </span>
                  <StatusBadge status={c.status} />
                </div>
                <Link
                  to={portalCasePath(c.id)}
                  className="mt-1 block text-base font-semibold text-brand-900 hover:text-brand-700"
                >
                  {c.title}
                </Link>
                <p className="mt-1 text-sm text-brand-500">
                  {c.practiceArea} · Advocate: {c.leadAttorney}
                  {c.nextHearing && ` · Next hearing ${formatDate(c.nextHearing)}`}
                </p>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

/** One of the client's cases: coming hearings and shared documents. */
export function PortalCasePage() {
  const { caseId = '' } = useParams<{ caseId: string }>();
  const query = usePortalCase(caseId);
  const notFound = query.error instanceof ApiError && query.error.isNotFound;

  const back = (
    <Link
      to={PORTAL_PATH}
      className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-brand-600 hover:text-brand-800"
    >
      <ArrowLeft className="h-4 w-4" aria-hidden="true" />
      Your Cases
    </Link>
  );

  if (query.isPending) {
    return (
      <>
        {back}
        <Card>
          <LoadingState label="Loading the case…" />
        </Card>
      </>
    );
  }
  if (!query.data || notFound) {
    return (
      <>
        {back}
        <Card>
          <ErrorState
            title={notFound ? 'Case not found' : "Couldn't load the case"}
            error={query.error}
            onRetry={notFound ? undefined : () => query.refetch()}
          />
        </Card>
      </>
    );
  }

  const c = query.data;
  return (
    <>
      {back}
      <header className="mb-5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-brand-400">
            {c.caseNumber}
          </span>
          <StatusBadge status={c.status} />
        </div>
        <h1 className="mt-2 text-2xl font-bold text-brand-900">{c.title}</h1>
        <p className="mt-1 text-sm text-brand-500">
          {c.practiceArea} · Advocate: {c.leadAttorney}
          {c.courtName && ` · ${c.courtName}`} · Opened {formatDate(c.openedOn)}
        </p>
      </header>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader title="Coming Hearings" />
          <CardBody className="p-0">
            {c.hearings.length === 0 ? (
              <p className="px-5 py-6 text-sm text-brand-500">No hearings scheduled.</p>
            ) : (
              <ul className="divide-y divide-brand-100" aria-label="Coming hearings">
                {c.hearings.map((h) => (
                  <li key={`${h.date}-${h.time}-${h.purpose}`} className="px-5 py-3">
                    <p className="text-sm font-medium text-brand-900">{h.purpose}</p>
                    <p className="mt-1 flex items-center gap-1.5 text-xs text-brand-500">
                      <CalendarClock className="h-3.5 w-3.5" aria-hidden="true" />
                      {formatDate(h.date)} · {h.time ?? 'time to be confirmed'} · {h.court}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Documents Shared With You" />
          <CardBody className="p-0">
            {c.documents.length === 0 ? (
              <p className="px-5 py-6 text-sm text-brand-500">
                No documents have been shared with you yet.
              </p>
            ) : (
              <ul className="divide-y divide-brand-100" aria-label="Shared documents">
                {c.documents.map((d) => (
                  <li key={d.id} className="flex items-center gap-3 px-5 py-3">
                    <FileText className="h-4 w-4 text-brand-400" aria-hidden="true" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-brand-900">{d.name}</p>
                      <p className="text-xs text-brand-500">
                        {d.type} · {d.size} · Shared {formatDate(d.sharedOn)}
                      </p>
                    </div>
                    <a
                      href={d.downloadUrl}
                      className="rounded-md p-2 text-brand-500 hover:bg-brand-50 hover:text-brand-800"
                      aria-label={`Download ${d.name}`}
                    >
                      <Download className="h-4 w-4" aria-hidden="true" />
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
      </div>
    </>
  );
}
