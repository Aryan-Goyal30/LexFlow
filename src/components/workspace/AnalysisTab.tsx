import { useId } from 'react';
import { CheckCircle2, Circle, Loader2, Sparkles } from 'lucide-react';
import type { Case, CaseDocument } from '../../types';
import type { CaseAnalysis } from '../../types/ai';
import type { AiAssistant } from '../../hooks/useAiAssistant';
import { Card, CardBody, CardHeader } from '../ui/Card';
import { Button } from '../ui/Button';
import { AiStatusPill, DecisionSupportNote, NotConnectedNotice } from './AiNotices';
import { PrecedentCard } from './PrecedentCard';

/** What a full analysis will produce, in the order a lawyer reviews it. */
const OUTPUT_SECTIONS = [
  {
    title: 'Key facts',
    detail: 'Drawn from the case record and each document, each linked to its source.',
  },
  {
    title: 'Legal issues',
    detail: 'The questions of law the matter turns on, tied to the facts behind them.',
  },
  {
    title: 'Relevant precedents',
    detail: 'Judgments retrieved from a collection of past judgments, ranked by relevance.',
  },
  {
    title: 'Similarities & differences',
    detail: 'How each precedent compares with the facts of this case.',
  },
  {
    title: 'Contradictions',
    detail: 'Places where documents or statements in the record conflict.',
  },
  {
    title: 'Outcome assessment',
    detail:
      'An evidence-supported view, offered only where precedents support it. A later stage, after search quality has been evaluated.',
  },
];

export function AnalysisTab({ legalCase: c, ai }: { legalCase: Case; ai: AiAssistant }) {
  const { status, result, error } = ai.analysis;
  const unavailableId = useId();
  const stored = c.documents.filter((d) => d.hasFile).length;
  const inputs = [
    {
      label: 'Case summary',
      ready: c.description.trim().length > 0,
      note: `${c.description.length} characters`,
    },
    {
      label: 'Documents',
      ready: c.documents.length > 0,
      note: `${c.documents.length} on file, ${stored} with a stored file`,
    },
    {
      label: 'Matter timeline',
      ready: c.timeline.length > 0,
      note: `${c.timeline.length} events`,
    },
    {
      label: 'Parties & forum',
      ready: Boolean(c.courtName && c.opposingParty),
      note:
        c.courtName && c.opposingParty
          ? c.courtName
          : `Missing: ${[!c.courtName && 'court', !c.opposingParty && 'opposing party'].filter(Boolean).join(' and ')}`,
    },
  ];

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        <Card>
          <CardHeader title="Case Analysis" action={<AiStatusPill status={status} />} />
          <CardBody className="space-y-4">
            <p className="text-sm leading-relaxed text-brand-700">
              Once an AI service is connected, the assistant will read this case and its documents,
              pick out the facts and legal issues, find relevant precedents, and set out how they
              compare, for you to review and verify.
            </p>

            {status === 'not_connected' && (
              <NotConnectedNotice feature="AI analysis">
                No AI service is connected in this version of LexFlow, so nothing on this tab is
                generated. The Analysis Inputs panel is read directly from the case record.
              </NotConnectedNotice>
            )}
            {status === 'error' && error && (
              <p
                role="alert"
                className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-inset ring-red-600/20"
              >
                {error} No analysis is shown.
              </p>
            )}

            <div className="flex flex-wrap items-center gap-3">
              <Button
                onClick={() => void ai.runAnalysis()}
                disabled={!ai.connected || status === 'running'}
                aria-describedby={!ai.connected ? unavailableId : undefined}
              >
                {status === 'running' ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Sparkles className="h-4 w-4" aria-hidden="true" />
                )}
                {status === 'running' ? 'Analysing…' : result ? 'Re-run analysis' : 'Analyse case'}
              </Button>
              {!ai.connected && (
                <span id={unavailableId} className="text-xs text-brand-500">
                  Unavailable: no AI service is connected.
                </span>
              )}
            </div>
            <DecisionSupportNote />
          </CardBody>
        </Card>

        {status === 'ready' && result ? (
          <AnalysisResults analysis={result} documents={c.documents} />
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
          <p className="text-xs text-brand-500">
            What the assistant would read from this case. This panel uses real case data.
          </p>
          <ul className="space-y-3">
            {inputs.map((input) => (
              <li key={input.label} className="flex items-start gap-2.5">
                {input.ready ? (
                  <CheckCircle2
                    className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600"
                    aria-label="Ready"
                  />
                ) : (
                  <Circle className="mt-0.5 h-4 w-4 shrink-0 text-brand-300" aria-label="Missing" />
                )}
                <div>
                  <p className="text-sm font-medium text-brand-800">{input.label}</p>
                  <p className="text-xs text-brand-500">{input.note}</p>
                </div>
              </li>
            ))}
          </ul>
        </CardBody>
      </Card>
    </div>
  );
}

/**
 * Renders an analysis returned by a connected service. Only fields in the
 * CaseAnalysis contract are used, and every fact shows which document it came
 * from. outcomeAssessment is deliberately not displayed: it is a later stage
 * (see DEVELOPMENT_BRIEF.md) and must not appear before it is evaluated.
 */
function AnalysisResults({
  analysis,
  documents,
}: {
  analysis: CaseAnalysis;
  documents: CaseDocument[];
}) {
  const documentName = (id?: string) =>
    id ? (documents.find((d) => d.id === id)?.name ?? 'a document no longer on file') : null;

  return (
    <>
      <Card>
        <CardHeader title={`Key Facts (${analysis.facts.length})`} />
        <CardBody>
          {analysis.facts.length === 0 ? (
            <p className="text-sm text-brand-500">No facts were extracted.</p>
          ) : (
            <ul className="space-y-2.5 text-sm text-brand-700">
              {analysis.facts.map((fact) => {
                const source = documentName(fact.sourceDocumentId);
                return (
                  <li key={fact.id}>
                    <p>{fact.statement}</p>
                    <p className="text-xs text-brand-500">
                      {source ? `Source: ${source}` : 'No source document cited. Verify manually.'}
                    </p>
                  </li>
                );
              })}
            </ul>
          )}
        </CardBody>
      </Card>
      <Card>
        <CardHeader title={`Legal Issues (${analysis.issues.length})`} />
        <CardBody>
          {analysis.issues.length === 0 ? (
            <p className="text-sm text-brand-500">No legal issues were identified.</p>
          ) : (
            <ol className="list-decimal space-y-1.5 pl-4 text-sm text-brand-700">
              {analysis.issues.map((issue) => (
                <li key={issue.id}>{issue.question}</li>
              ))}
            </ol>
          )}
        </CardBody>
      </Card>
      <Card>
        <CardHeader title={`Relevant Precedents (${analysis.precedents.length})`} />
        <CardBody className="space-y-3">
          {analysis.precedents.length === 0 ? (
            <p className="text-sm text-brand-500">No relevant precedents were found.</p>
          ) : (
            analysis.precedents.map((p) => <PrecedentCard key={p.id} precedent={p} />)
          )}
        </CardBody>
      </Card>
      {analysis.contradictions.length > 0 && (
        <Card>
          <CardHeader title={`Contradictions (${analysis.contradictions.length})`} />
          <CardBody>
            <ul className="space-y-2.5 text-sm text-brand-700">
              {analysis.contradictions.map((item) => (
                <li key={item.id}>
                  <p>{item.description}</p>
                  {item.sourceDocumentIds.length > 0 && (
                    <p className="text-xs text-brand-500">
                      Sources: {item.sourceDocumentIds.map((id) => documentName(id)).join('; ')}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
      )}
    </>
  );
}
