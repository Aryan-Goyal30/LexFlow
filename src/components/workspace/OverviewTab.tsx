import { User2, Gavel, CalendarClock, Clock, Building2, type LucideIcon } from 'lucide-react';
import type { Case } from '../../types';
import { Card, CardBody, CardHeader } from '../ui/Card';
import { formatDate } from '../../lib/format';

export function OverviewTab({ legalCase: c }: { legalCase: Case }) {
  return (
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
  );
}

function DetailRow({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) {
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
