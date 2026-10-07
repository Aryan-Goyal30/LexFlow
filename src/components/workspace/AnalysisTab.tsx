import { CheckCircle2, Circle, Sparkles } from 'lucide-react';
import type { Case } from '../../types';
import type { CaseAnalysis } from '../../types/ai';
import type { AiAssistant } from '../../hooks/useAiAssistant';
import { Card, CardBody, CardHeader } from '../ui/Card';
import { Button } from '../ui/Button';
import { AiStatusPill, DecisionSupportNote, NotConnectedNotice } from './AiNotices';
import { PrecedentCard } from './PrecedentCard';

/** What a full analysis will produce, in the order a lawyer reviews it. */
const OUTPUT_SECTIONS = [
  { title: 'Key facts', detail: 'Extracted from the case record and each document, each linked to its source.' },
  { title: 'Legal issues', detail: 'The questions of law the matter turns on, tied to the facts behind them.' },
  { title: 'Relevant precedents', detail: 'Judgments retrieved from the legal knowledge base, ranked by relevance.' },
  { title: 'Similarities & differences', detail: 'How each precedent compares with the facts of this case.' },
  { title: 'Contradictions', detail: 'Places where documents or statements in the record conflict.' },
  { title: 'Outcome assessment', detail: 'An evidence-supported view, offered only where precedents support it. Later milestone.' },
];

export function AnalysisTab({ legalCase: c, ai }: { legalCase: Case; ai: AiAssistant }) {
  const uploaded = c.documents.filter((d) => d.url).length;
  const inputs = [
    { label: 'Case summary', ready: c.description.trim().length > 0, note: `${c.description.length} characters` },
    { label: 'Documents', ready: c.documents.length > 0, note: `${c.documents.length} on file, ${uploaded} uploaded this session` },
    { label: 'Matter timeline', ready: c.timeline.length > 0, note: `${c.timeline.length} events` },
    { label: 'Parties & forum', ready: Boolean(c.courtName && c.opposingParty), note: c.courtName ?? 'Court not set' },
  ];

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        <Card>
          <CardHeader title="Case Analysis" action={<AiStatusPill status={ai.status} />} />
          <CardBody className="space-y-4">
            <p className="text-sm leading-relaxed text-brand-700">
              Reads this case and its documents, extracts the facts and legal issues, retrieves
              relevant precedents, and lays out how they compare — for you to review and verify.
            </p>

            {ai.status === 'not_connected' && (
              <NotConnectedNotice feature="AI analysis">
                The workspace and data contract are ready; the model and legal knowledge base are
                a later milestone. Until then, nothing here is generated and no analysis is shown.
              </NotConnectedNotice>
            )}
            {ai.status === 'error' && ai.error && (
              <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-inset ring-red-600/20">
                {ai.error}
              </p>
            )}

            <div className="flex flex-wrap items-center gap-3">
              <Button
                onClick={ai.runAnalysis}
                disabled={!ai.connected || ai.status === 'running'}
                title={ai.connected ? undefined : 'No AI service is connected'}
              >
                <Sparkles className="h-4 w-4" />
                {ai.analysis ? 'Re-run analysis' : 'Analyse case'}
              </Button>
            </div>
            <DecisionSupportNote />
          </CardBody>
        </Card>

        {ai.analysis ? (
          <AnalysisResults analysis={ai.analysis} />
        ) : (
          <Card>
            <CardHeader title="What the analysis will contain" />
            <CardBody className="p-0">
              <ol className="divide-y divide-brand-100">
                {OUTPUT_SECTIONS.map((section) => (
                  <li key={section.title} className="px-5 py-3">
                    <p className="text-sm font-medium text-brand-900">{section.title}</p>
                    <p className="mt-0.5 text-sm text-brand-500">{section.detail}</p>
                  </li>
                ))}
              </ol>
            </CardBody>
          </Card>
        )}
      </div>

      <Card className="self-start">
        <CardHeader title="Analysis Inputs" />
        <CardBody className="space-y-3">
          <p className="text-xs text-brand-500">What the assistant will read from this case.</p>
          {inputs.map((input) => (
            <div key={input.label} className="flex items-start gap-2.5">
              {input.ready ? (
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
              ) : (
                <Circle className="mt-0.5 h-4 w-4 shrink-0 text-brand-300" />
              )}
              <div>
                <p className="text-sm font-medium text-brand-800">{input.label}</p>
                <p className="text-xs text-brand-500">{input.note}</p>
              </div>
            </div>
          ))}
        </CardBody>
      </Card>
    </div>
  );
}

/** Renders a real analysis once a connected service returns one. */
function AnalysisResults({ analysis }: { analysis: CaseAnalysis }) {
  return (
    <>
      <Card>
        <CardHeader title={`Key Facts (${analysis.facts.length})`} />
        <CardBody>
          <ul className="list-disc space-y-1.5 pl-4 text-sm text-brand-700">
            {analysis.facts.map((fact) => (
              <li key={fact.id}>{fact.statement}</li>
            ))}
          </ul>
        </CardBody>
      </Card>
      <Card>
        <CardHeader title={`Legal Issues (${analysis.issues.length})`} />
        <CardBody>
          <ol className="list-decimal space-y-1.5 pl-4 text-sm text-brand-700">
            {analysis.issues.map((issue) => (
              <li key={issue.id}>{issue.question}</li>
            ))}
          </ol>
        </CardBody>
      </Card>
      <Card>
        <CardHeader title={`Relevant Precedents (${analysis.precedents.length})`} />
        <CardBody className="space-y-3">
          {analysis.precedents.map((p) => (
            <PrecedentCard key={p.id} precedent={p} />
          ))}
        </CardBody>
      </Card>
      {analysis.contradictions.length > 0 && (
        <Card>
          <CardHeader title={`Contradictions (${analysis.contradictions.length})`} />
          <CardBody>
            <ul className="list-disc space-y-1.5 pl-4 text-sm text-brand-700">
              {analysis.contradictions.map((item) => (
                <li key={item.id}>{item.description}</li>
              ))}
            </ul>
          </CardBody>
        </Card>
      )}
    </>
  );
}
