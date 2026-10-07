import { useState, type FormEvent } from 'react';
import { BookOpenText, Search } from 'lucide-react';
import type { Case } from '../../types';
import type { AiAssistant } from '../../hooks/useAiAssistant';
import { Card, CardBody, CardHeader } from '../ui/Card';
import { Button } from '../ui/Button';
import { DecisionSupportNote, NotConnectedNotice } from './AiNotices';
import { PrecedentCard } from './PrecedentCard';

export function ResearchTab({ legalCase: c, ai }: { legalCase: Case; ai: AiAssistant }) {
  const [query, setQuery] = useState('');

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (query.trim()) ai.searchPrecedents(query.trim());
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Precedent Research" />
        <CardBody className="space-y-4">
          <p className="text-sm leading-relaxed text-brand-700">
            Search historical judgments for this {c.practiceArea.toLowerCase()} matter. Results are
            ranked against this case's facts, with the points of similarity and difference set out
            for each.
          </p>

          <form onSubmit={handleSubmit} className="flex flex-col gap-2 sm:flex-row">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-brand-400" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g. interim injunction, deceptively similar trade mark"
                className="input-field pl-9"
                disabled={!ai.connected}
              />
            </div>
            <Button type="submit" disabled={!ai.connected || !query.trim() || ai.status === 'running'}>
              Search precedents
            </Button>
          </form>

          {!ai.connected && (
            <NotConnectedNotice feature="Precedent research">
              Searching needs a legal knowledge base of judgments and a retrieval service, both
              planned for a later milestone. No precedents are shown until real sources are
              connected.
            </NotConnectedNotice>
          )}
          <DecisionSupportNote />
        </CardBody>
      </Card>

      {ai.precedents && (
        <Card>
          <CardHeader title={`Results (${ai.precedents.length})`} />
          <CardBody className="space-y-3">
            {ai.precedents.length === 0 ? (
              <p className="text-sm text-brand-500">No matching precedents found.</p>
            ) : (
              ai.precedents.map((p) => <PrecedentCard key={p.id} precedent={p} />)
            )}
          </CardBody>
        </Card>
      )}

      {!ai.precedents && (
        <div className="flex flex-col items-center justify-center rounded-lg border border-brand-100 bg-white px-6 py-12 text-center">
          <BookOpenText className="h-9 w-9 text-brand-300" strokeWidth={1.5} />
          <p className="mt-3 text-sm font-medium text-brand-700">No research yet</p>
          <p className="mt-1 max-w-sm text-sm text-brand-500">
            Precedents you find and compare for this case will be collected here.
          </p>
        </div>
      )}
    </div>
  );
}
