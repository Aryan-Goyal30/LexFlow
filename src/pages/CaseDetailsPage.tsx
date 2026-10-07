import { Link, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Scale,
  User2,
  Gavel,
  CalendarClock,
  FileText,
  Clock,
  Building2,
} from 'lucide-react';
import { useCases } from '../context/CasesContext';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { StatusBadge, PriorityBadge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { formatDate } from '../lib/format';

export function CaseDetailsPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const { getCaseById } = useCases();
  const legalCase = caseId ? getCaseById(caseId) : undefined;

  if (!legalCase) {
    return (
      <Card className="flex flex-col items-center justify-center px-6 py-16 text-center">
        <Scale className="h-10 w-10 text-brand-300" strokeWidth={1.5} />
        <p className="mt-3 text-sm font-medium text-brand-700">Case not found</p>
        <p className="mt-1 text-sm text-brand-500">
          This matter may have been removed or the link is incorrect.
        </p>
        <Link to="/app/cases" className="mt-4">
          <Button variant="secondary">Back to Cases</Button>
        </Link>
      </Card>
    );
  }

  const c = legalCase;

  return (
    <>
      <Link
        to="/app/cases"
        className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-brand-600 hover:text-brand-800"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Cases
      </Link>

      <div className="mb-6 flex flex-col gap-3 border-b border-brand-100 pb-6 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-brand-400">
              {c.caseNumber}
            </span>
            <StatusBadge status={c.status} />
            <PriorityBadge priority={c.priority} />
          </div>
          <h1 className="mt-2 text-2xl font-bold text-brand-900">{c.title}</h1>
          <p className="mt-1 text-sm text-brand-500">
            {c.practiceArea} · Opened {formatDate(c.openedOn)}
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader title="Summary" />
            <CardBody>
              <p className="text-sm leading-relaxed text-brand-700">{c.description}</p>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Matter Timeline" />
            <CardBody>
              <ol className="relative space-y-5 border-l border-brand-200 pl-6">
                {c.timeline.map((event) => (
                  <li key={event.id} className="relative">
                    <span className="absolute -left-[27px] top-1 grid h-3 w-3 place-items-center rounded-full border-2 border-white bg-brand-500" />
                    <p className="text-sm font-medium text-brand-900">{event.label}</p>
                    <p className="text-xs text-brand-400">{formatDate(event.date)}</p>
                    <p className="mt-1 text-sm text-brand-600">{event.description}</p>
                  </li>
                ))}
              </ol>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title={`Documents (${c.documents.length})`} />
            <CardBody className="p-0">
              {c.documents.length === 0 ? (
                <p className="px-5 py-6 text-sm text-brand-500">
                  No documents attached to this matter yet.
                </p>
              ) : (
                <ul className="divide-y divide-brand-100">
                  {c.documents.map((doc) => (
                    <li key={doc.id} className="flex items-center gap-3 px-5 py-3">
                      <span className="rounded-md bg-brand-50 p-2 text-brand-500">
                        <FileText className="h-4 w-4" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-brand-900">{doc.name}</p>
                        <p className="text-xs text-brand-500">
                          {doc.type} · {doc.size} · {formatDate(doc.uploadedOn)}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader title="Case Details" />
            <CardBody className="space-y-4">
              <DetailRow icon={User2} label="Client" value={c.clientName} />
              <DetailRow icon={Gavel} label="Lead Advocate" value={c.leadAttorney} />
              <DetailRow icon={Building2} label="Court" value={c.courtName ?? 'Not assigned'} />
              <DetailRow icon={User2} label="Opposing Party" value={c.opposingParty ?? '—'} />
              <DetailRow
                icon={CalendarClock}
                label="Next Hearing"
                value={c.nextHearing ? formatDate(c.nextHearing) : 'None scheduled'}
              />
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Hearings" />
            <CardBody className="p-0">
              {c.hearings.length === 0 ? (
                <p className="px-5 py-6 text-sm text-brand-500">No hearings scheduled.</p>
              ) : (
                <ul className="divide-y divide-brand-100">
                  {c.hearings.map((h) => (
                    <li key={h.id} className="px-5 py-3">
                      <p className="text-sm font-medium text-brand-900">{h.purpose}</p>
                      <p className="mt-1 flex items-center gap-1.5 text-xs text-brand-500">
                        <Clock className="h-3.5 w-3.5" />
                        {formatDate(h.date)} · {h.time} · {h.court}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>
        </div>
      </div>
    </>
  );
}

function DetailRow({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof User2;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <span className="mt-0.5 rounded-md bg-brand-50 p-1.5 text-brand-500">
        <Icon className="h-4 w-4" />
      </span>
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-brand-400">{label}</p>
        <p className="text-sm text-brand-800">{value}</p>
      </div>
    </div>
  );
}
