import { Fragment, useId, useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, Circle, FileText, Loader2, Sparkles } from 'lucide-react';
import type { Case } from '../../types';
import type { AnalysisRun, AnalysisSetup, AnalysisSource } from '../../types/ai';
import {
  isActive,
  useAnalysisRun,
  useAnalysisRuns,
  useAnalysisSetup,
  useStartAnalysis,
} from '../../hooks/useCaseAnalysis';
import { documentTextPath } from '../../lib/paths';
import { formatDate, formatTime } from '../../lib/format';
import { Card, CardBody, CardHeader } from '../ui/Card';
import { Button } from '../ui/Button';
import {
  AiStatusPill,
  DecisionSupportNote,
  UnavailableNotice,
  type AiPillStatus,
} from './AiNotices';
import { PrecedentCard } from './PrecedentCard';
import { ExportBrief, FindingReview, ReviewProgress } from './FindingReview';
import { useFindingReviews } from '../../hooks/useFindingReviews';
import { errorMessage } from '../../services/api/client';

const alertClass =
  'rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-inset ring-red-600/20';

const eligibleIds = (setup: AnalysisSetup) =>
  setup.documents
    .filter((d) => d.eligible)
    .map((d) => d.id)
    .join(',');
const when = (iso: string) => `${formatDate(iso.slice(0, 10))}, ${formatTime(iso)}`;
const place = (page: number | null, section: number) =>
  page !== null ? `page ${page}` : `part ${section}`;

/**
 * AI case analysis (Phase 5). The server decides whether a case can be
 * analysed, sends the selected text to the configured provider and returns
 * only items it could verify against that text; this tab chooses documents,
 * asks for explicit confirmation of what is sent, follows the run and shows
 * the result with a link to the source of every claim.
 */
export function AnalysisTab({ legalCase: c }: { legalCase: Case }) {
  const setup = useAnalysisSetup(c);
  const history = useAnalysisRuns(c.id);
  const [chosenRunId, setChosenRunId] = useState<string | null>(null);
  const runId = chosenRunId ?? setup.data?.activeRunId ?? history.data?.items[0]?.id ?? null;
  const run = useAnalysisRun(c.id, runId);

  let pill: AiPillStatus = 'idle';
  if (setup.data && !setup.data.available) pill = 'unavailable';
  else if (run.data) pill = run.data.status;

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        <Card>
          <CardHeader title="Case Analysis" action={<AiStatusPill status={pill} />} />
          <CardBody className="space-y-4">
            {setup.isPending && (
              <p role="status" className="text-sm text-brand-500">
                Checking whether analysis is available…
              </p>
            )}
            {setup.isError && (
              <p role="alert" className={alertClass}>
                Couldn&apos;t check whether analysis is available. {setup.error.message}
              </p>
            )}
            {setup.data && !setup.data.available && (
              <UnavailableNotice feature="AI analysis">
                {setup.data.unavailableReason} Nothing on this tab is generated while analysis is
                unavailable.
              </UnavailableNotice>
            )}
            {setup.data?.available && (
              <StartForm
                // A new start form (fresh selection, unconfirmed) whenever the active
                // run or the documents that can be chosen change.
                key={`${setup.data.activeRunId ?? 'none'}|${eligibleIds(setup.data)}`}
                caseId={c.id}
                setup={setup.data}
                onStarted={setChosenRunId}
              />
            )}
            <DecisionSupportNote />
          </CardBody>
        </Card>

        {runId !== null && (
          <RunView
            caseId={c.id}
            run={run.data}
            loading={run.isPending}
            error={run.isError ? run.error.message : null}
          />
        )}
      </div>

      <div className="space-y-6 self-start">
        <RunHistory
          runs={history.data?.items ?? []}
          loading={history.isPending}
          selected={runId}
          onSelect={setChosenRunId}
        />
        <InputsPanel legalCase={c} />
      </div>
    </div>
  );
}

function StartForm({
  caseId,
  setup,
  onStarted,
}: {
  caseId: string;
  setup: AnalysisSetup;
  onStarted: (runId: string) => void;
}) {
  const start = useStartAnalysis(caseId);
  const reasonId = useId();
  const eligible = setup.documents.filter((d) => d.eligible);
  const [picked, setPicked] = useState<Set<string>>(
    () => new Set(eligible.slice(0, setup.limits.maxDocuments).map((d) => d.id)),
  );
  const [confirmed, setConfirmed] = useState(false);
  const provider = setup.providerLabel ?? 'the AI provider';

  const toggle = (id: string) =>
    setPicked((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  let blocked: string | null = setup.cannotRunReason;
  if (!blocked && eligible.length === 0) blocked = 'No document of this case has text ready yet.';
  else if (!blocked && picked.size === 0) blocked = 'Select at least one document.';
  else if (!blocked && picked.size > setup.limits.maxDocuments)
    blocked = `Select at most ${setup.limits.maxDocuments} documents.`;
  else if (!blocked && !confirmed) blocked = 'Confirm what will be sent before starting.';

  const submit = () =>
    start.mutate(
      { documentIds: [...picked], confirmTransmission: true },
      {
        onSuccess: (run) => {
          setConfirmed(false);
          onStarted(run.id);
        },
      },
    );

  return (
    <div className="space-y-4">
      <div
        role="note"
        aria-label="What leaves this computer"
        className="rounded-lg border border-amber-200 bg-amber-50/60 p-4 text-sm leading-relaxed text-amber-900"
      >
        <p className="font-medium">What leaves this computer</p>
        <p className="mt-1">
          Starting an analysis sends the text of the selected documents, with the case summary and
          timeline (at most {setup.limits.maxInputChars.toLocaleString('en-IN')} characters), and
          any matching judgment passages from the LexFlow server to <strong>{provider}</strong>
          {setup.model ? ` (model ${setup.model})` : ''}. How the provider keeps and uses that text
          is governed by its terms, not by LexFlow.
          {setup.sampleOnly && ' On this server only sample (fictional) cases may be analysed.'}
        </p>
        {setup.provider === 'scripted' && (
          <p className="mt-1 font-medium">
            This server uses a scripted test provider: results are canned test output, not AI.
          </p>
        )}
      </div>

      <fieldset>
        <legend className="text-sm font-medium text-brand-900">Documents to analyse</legend>
        {setup.documents.length === 0 ? (
          <p className="mt-1 text-sm text-brand-500">This case has no documents.</p>
        ) : (
          <ul className="mt-2 space-y-1.5">
            {setup.documents.map((d) => (
              <li key={d.id}>
                <label className="flex items-start gap-2 text-sm text-brand-800">
                  <input
                    type="checkbox"
                    className="mt-0.5"
                    checked={picked.has(d.id)}
                    disabled={!d.eligible}
                    onChange={() => toggle(d.id)}
                  />
                  <span>
                    {d.name}
                    {!d.eligible && <span className="text-brand-500"> (text not ready)</span>}
                    {d.eligible && d.pageCount !== null && (
                      <span className="text-brand-500"> · {d.pageCount} pages</span>
                    )}
                  </span>
                </label>
              </li>
            ))}
          </ul>
        )}
      </fieldset>

      <label className="flex items-start gap-2 text-sm text-brand-800">
        <input
          type="checkbox"
          className="mt-0.5"
          checked={confirmed}
          onChange={(e) => setConfirmed(e.target.checked)}
        />
        <span>I confirm that the selected text may be sent to {provider}.</span>
      </label>

      {start.isError && (
        <p role="alert" className={alertClass}>
          The analysis was not started. {start.error.message}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Button
          onClick={submit}
          disabled={blocked !== null || start.isPending}
          aria-describedby={blocked ? reasonId : undefined}
        >
          {start.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <Sparkles className="h-4 w-4" aria-hidden="true" />
          )}
          {start.isPending ? 'Starting…' : 'Analyse case'}
        </Button>
        {blocked && (
          <span id={reasonId} className="text-xs text-brand-500">
            {blocked}
          </span>
        )}
      </div>
    </div>
  );
}

function RunView({
  caseId,
  run,
  loading,
  error,
}: {
  caseId: string;
  run: AnalysisRun | undefined;
  loading: boolean;
  error: string | null;
}) {
  if (error) {
    return (
      <p role="alert" className={alertClass}>
        Couldn&apos;t load the analysis. {error} No result is shown.
      </p>
    );
  }
  if (loading || !run) {
    return (
      <p role="status" className="text-sm text-brand-500">
        Loading the analysis…
      </p>
    );
  }
  if (isActive(run)) {
    return (
      <Card>
        <CardBody>
          <p role="status" className="flex items-center gap-2 text-sm text-brand-700">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            {run.status === 'queued'
              ? 'Waiting for the worker to start the analysis…'
              : 'Analysing… this can take a minute or two.'}
          </p>
        </CardBody>
      </Card>
    );
  }
  if (run.status === 'failed' || !run.result) {
    return (
      <p role="alert" className={alertClass}>
        The analysis failed: {run.reason ?? 'no reason was recorded.'} No result is shown.
      </p>
    );
  }
  return <AnalysisResults caseId={caseId} run={run} />;
}

function SourceLine({
  caseId,
  source,
  changed,
}: {
  caseId: string;
  source: AnalysisSource;
  changed: boolean;
}) {
  return (
    <div className="mt-1.5 border-l-2 border-brand-200 pl-3">
      <blockquote className="text-sm italic text-brand-600">
        &ldquo;{source.quote}&rdquo;
      </blockquote>
      <Link
        to={documentTextPath(caseId, source.documentId, source.sectionNumber)}
        className="mt-0.5 inline-flex items-center gap-1 text-xs font-medium text-brand-700 underline-offset-2 hover:underline"
      >
        <FileText className="h-3.5 w-3.5" aria-hidden="true" />
        {source.documentName}, {place(source.pageNumber, source.sectionNumber)}
      </Link>
      {changed && (
        <span className="ml-1.5 text-xs font-medium text-amber-800">
          (changed since this analysis)
        </span>
      )}
    </div>
  );
}

/**
 * A validated result. Every fact and contradiction shows its verified quote
 * with a link to the document page; every precedent links to the judgment
 * passage. Removed items are counted with their reasons. No outcome
 * assessment exists in the contract, so none can be shown.
 *
 * Phase 6: every finding carries its lawyer-review state ("Unreviewed" until
 * a lawyer decides); reviewers accept, edit, reject or clear it in place.
 */
function AnalysisResults({ caseId, run }: { caseId: string; run: AnalysisRun }) {
  const result = run.result!;
  const evidence = run.evidence;
  const changed = new Set(evidence?.changed ?? []);
  const reviews = useFindingReviews(caseId, run.id);
  const canReview = reviews.data?.canReview ?? false;
  const review = (id: string, label: string, text: string, sourceChanged = false) => {
    const current = reviews.data?.items.find((i) => i.findingId === id);
    return current ? (
      <FindingReview
        caseId={caseId}
        runId={run.id}
        label={label}
        originalText={text}
        review={current}
        canReview={canReview}
        sourceChanged={sourceChanged}
      />
    ) : null;
  };
  return (
    <>
      <Card>
        <CardHeader title="Analysis result" />
        <CardBody className="space-y-3 text-sm text-brand-700">
          {run.provider === 'scripted' && (
            <p className="rounded-md bg-amber-50 px-3 py-2 font-medium text-amber-900 ring-1 ring-inset ring-amber-600/30">
              Scripted test output — not AI. Produced by the test provider for checking LexFlow.
            </p>
          )}
          <p className="text-xs text-brand-500">
            {run.provider === 'gemini' ? 'Google Gemini API' : run.provider} · model {run.model} ·
            prompt {run.promptVersion}
            {run.finishedAt && ` · ${when(run.finishedAt)}`}
            {run.requestedBy && ` · started by ${run.requestedBy.name}`}
          </p>
          {evidence && (
            <p className="text-xs text-brand-500">
              Sent: {evidence.passages} passages from {evidence.documents} documents and{' '}
              {evidence.judgmentPassages} judgment passages (
              {evidence.characters.toLocaleString('en-IN')} characters).
              {evidence.truncated && ' Limits left some passages out.'}
            </p>
          )}
          {changed.size > 0 && (
            <p
              role="status"
              className="rounded-md bg-amber-50 px-3 py-2 text-amber-900 ring-1 ring-inset ring-amber-600/30"
            >
              <strong>Some sources changed after this analysis ran</strong> (
              {[...changed].join(', ')}): a document was re-extracted or deleted, or a judgment was
              removed. Quotes are shown as they were verified at the time; their links may open
              different text, or none.
            </p>
          )}
          {result.insufficientEvidence && (
            <p className="rounded-md bg-brand-50 px-3 py-2 text-brand-800 ring-1 ring-inset ring-brand-200">
              <strong>Not enough evidence for a useful analysis.</strong>{' '}
              {result.insufficientReason}
            </p>
          )}
          {result.removed.count > 0 && (
            <div className="rounded-md bg-brand-50 px-3 py-2 ring-1 ring-inset ring-brand-200">
              <p className="font-medium text-brand-800">
                {result.removed.count} {result.removed.count === 1 ? 'item was' : 'items were'}{' '}
                removed because {result.removed.count === 1 ? 'it' : 'they'} could not be verified
                against the sources:
              </p>
              <ul className="mt-1 list-disc pl-5 text-xs text-brand-600">
                {result.removed.reasons.map((r) => (
                  <li key={r.code}>
                    {r.message} ({r.count})
                  </li>
                ))}
              </ul>
            </div>
          )}
          <DecisionSupportNote />
          {reviews.isPending && (
            <p className="text-xs text-brand-500">Loading the lawyer review…</p>
          )}
          {reviews.isError && (
            <div role="alert" className={alertClass}>
              The lawyer review could not be loaded: {errorMessage(reviews.error)}{' '}
              <button
                type="button"
                className="font-medium underline underline-offset-2"
                onClick={() => void reviews.refetch()}
              >
                Try again
              </button>
            </div>
          )}
          {reviews.data && (
            <>
              <ReviewProgress summary={reviews.data.summary} />
              <ExportBrief caseId={caseId} runId={run.id} summary={reviews.data.summary} />
            </>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title={`Key Facts (${result.facts.length})`} />
        <CardBody>
          {result.facts.length === 0 ? (
            <p className="text-sm text-brand-500">No verified facts.</p>
          ) : (
            <ul className="space-y-4 text-sm text-brand-800">
              {result.facts.map((fact) => (
                <li key={fact.id} id={`analysis-fact-${fact.id}`}>
                  <p>
                    <span className="mr-1.5 text-xs font-semibold text-brand-400">{fact.id}</span>
                    {fact.statement}
                  </p>
                  <SourceLine
                    caseId={caseId}
                    source={fact.source}
                    changed={changed.has(fact.source.evidenceId)}
                  />
                  {review(
                    fact.id,
                    `Fact ${fact.id}`,
                    fact.statement,
                    changed.has(fact.source.evidenceId),
                  )}
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title={`Legal Issues (${result.issues.length})`} />
        <CardBody>
          {result.issues.length === 0 ? (
            <p className="text-sm text-brand-500">No issues tied to verified facts.</p>
          ) : (
            <ol className="list-decimal space-y-2 pl-4 text-sm text-brand-800">
              {result.issues.map((issue) => (
                <li key={issue.id}>
                  {issue.question}{' '}
                  <span className="text-xs text-brand-500">
                    (rests on{' '}
                    {issue.factIds.map((factId, i) => (
                      <Fragment key={factId}>
                        {i > 0 && ', '}
                        <a
                          href={`#analysis-fact-${factId}`}
                          className="font-medium text-brand-700 underline-offset-2 hover:underline"
                        >
                          {factId}
                        </a>
                      </Fragment>
                    ))}
                    )
                  </span>
                  {review(issue.id, `Issue ${issue.id}`, issue.question)}
                </li>
              ))}
            </ol>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title={`Precedent Comparisons (${result.precedents.length})`} />
        <CardBody className="space-y-3">
          {!result.precedentsAvailable ? (
            <p className="text-sm text-brand-600">
              No precedents were available for comparison: no judgment in the collection matched
              this case, so none was sent and none is shown.
            </p>
          ) : result.precedents.length === 0 ? (
            <p className="text-sm text-brand-500">
              None of the retrieved judgments was compared with this case.
            </p>
          ) : (
            result.precedents.map((p) => (
              <div key={p.id}>
                <PrecedentCard precedent={p} />
                {review(p.id, `Precedent comparison ${p.id}`, p.summary, changed.has(p.evidenceId))}
              </div>
            ))
          )}
        </CardBody>
      </Card>

      {result.contradictions.length > 0 && (
        <Card>
          <CardHeader title={`Contradictions (${result.contradictions.length})`} />
          <CardBody>
            <ul className="space-y-4 text-sm text-brand-800">
              {result.contradictions.map((item) => (
                <li key={item.id}>
                  <p>{item.description}</p>
                  {item.sources.map((source) => (
                    <SourceLine
                      key={`${source.evidenceId}-${source.quote}`}
                      caseId={caseId}
                      source={source}
                      changed={changed.has(source.evidenceId)}
                    />
                  ))}
                  {review(
                    item.id,
                    `Contradiction ${item.id}`,
                    item.description,
                    item.sources.some((s) => changed.has(s.evidenceId)),
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

function RunHistory({
  runs,
  loading,
  selected,
  onSelect,
}: {
  runs: {
    id: string;
    status: AiPillStatus;
    model: string;
    createdAt: string;
    requestedBy: { name: string } | null;
  }[];
  loading: boolean;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <Card>
      <CardHeader title="Analysis history" />
      <CardBody className="p-0">
        {loading ? (
          <p className="px-5 py-3 text-sm text-brand-500">Loading…</p>
        ) : runs.length === 0 ? (
          <p className="px-5 py-3 text-sm text-brand-500">No analysis has been run on this case.</p>
        ) : (
          <ul className="divide-y divide-brand-100">
            {runs.map((r) => (
              <li key={r.id}>
                <button
                  type="button"
                  onClick={() => onSelect(r.id)}
                  aria-current={r.id === selected ? 'true' : undefined}
                  className={`w-full px-5 py-2.5 text-left text-sm hover:bg-brand-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-500 ${r.id === selected ? 'bg-brand-50' : ''}`}
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className="text-brand-800">{when(r.createdAt)}</span>
                    <AiStatusPill status={r.status} />
                  </span>
                  <span className="block text-xs text-brand-500">
                    {r.model}
                    {r.requestedBy && ` · ${r.requestedBy.name}`}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}

function InputsPanel({ legalCase: c }: { legalCase: Case }) {
  // Review decisions are shown on the timeline but never sent to the model.
  const caseEvents = c.timeline.filter((e) => e.kind !== 'review').length;
  const inputs = [
    {
      label: 'Case summary',
      ready: c.description.trim().length > 0,
      note: `${c.description.length} characters (background only, never cited)`,
    },
    {
      label: 'Documents with text',
      ready: c.documents.some((d) => d.processing?.status === 'ready'),
      note: `${c.documents.filter((d) => d.processing?.status === 'ready').length} of ${c.documents.length} on file`,
    },
    {
      label: 'Matter timeline',
      ready: caseEvents > 0,
      note: `${caseEvents} events (the latest 30 are sent; lawyers' review decisions never are)`,
    },
  ];
  return (
    <Card>
      <CardHeader title="Analysis Inputs" />
      <CardBody className="space-y-3">
        <p className="text-xs text-brand-500">
          What an analysis reads from this case. Facts may cite only document passages.
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
  );
}
