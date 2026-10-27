import { useId, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, BookOpen, FlaskConical, Info, Loader2, Scale } from 'lucide-react';
import {
  useAssessmentHistory,
  useAssessments,
  useGenerateAssessment,
  useReviewAssessment,
} from '../../hooks/useAssessments';
import { judgmentPath } from '../../lib/paths';
import { formatDate, formatTime } from '../../lib/format';
import { errorMessage } from '../../services/api/client';
import type {
  Assessment,
  AssessmentResult,
  AssessmentReviewInput,
  AssessmentStance,
  AssessmentUncertainty,
} from '../../types/ai';
import { Card, CardBody, CardHeader } from '../ui/Card';
import { Button } from '../ui/Button';
import { SyntheticBadge } from '../research/Judgments';
import { ReviewStatusBadge } from './FindingReview';

/**
 * Outcome assessment (Phase 7): a synthetic-only engineering demonstration,
 * shown only when the server's setup reports `assessmentEnabled` (off by
 * default). An assessment rests only on what a lawyer accepted in this run;
 * every precedent, quote and reasoning step was verified by the server. It is
 * decision support: its uncertainty is a category, never a number, and it is
 * never shown as lawyer-approved until a reviewer accepts it.
 */

const when = (iso: string) => `${formatDate(iso.slice(0, 10))}, ${formatTime(iso)}`;
const place = (page: number | null, section: number) =>
  page !== null ? `page ${page}` : `part ${section}`;
const alertClass =
  'rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-inset ring-red-600/20';

const UNCERTAINTY: Record<AssessmentUncertainty, { label: string; className: string }> = {
  insufficient_basis: {
    label: 'Insufficient basis',
    className: 'bg-brand-100 text-brand-700 ring-brand-600/20',
  },
  mixed_evidence: {
    label: 'Mixed evidence',
    className: 'bg-amber-50 text-amber-800 ring-amber-600/30',
  },
  limited_support: {
    label: 'Limited support',
    className: 'bg-sky-50 text-sky-800 ring-sky-600/30',
  },
  evidence_supports_position: {
    label: 'Precedents support the position',
    className: 'bg-emerald-50 text-emerald-800 ring-emerald-600/30',
  },
};

const STANCE: Record<AssessmentStance, { label: string; className: string }> = {
  supports: { label: 'Supports', className: 'bg-emerald-50 text-emerald-800 ring-emerald-600/30' },
  cuts_against: { label: 'Cuts against', className: 'bg-red-50 text-red-800 ring-red-600/30' },
  does_not_resolve: {
    label: 'Does not resolve',
    className: 'bg-brand-50 text-brand-700 ring-brand-600/20',
  },
};

function Chip({ label, className }: { label: string; className: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${className}`}
    >
      {label}
    </span>
  );
}

export function AssessmentPanel({ caseId, runId }: { caseId: string; runId: string }) {
  const list = useAssessments(caseId, runId, true);
  const generate = useGenerateAssessment(caseId, runId);
  const [selected, setSelected] = useState<string | null>(null);
  const reasonId = useId();
  const items = list.data?.items ?? [];
  const shown = items.find((a) => a.id === selected) ?? items[0];

  return (
    <Card role="region" aria-label="Outcome assessment (decision support)">
      <CardHeader
        title="Outcome assessment (decision support)"
        action={<Chip label="Decision support" className={UNCERTAINTY.mixed_evidence.className} />}
      />
      <CardBody className="space-y-4 text-sm text-brand-700">
        <div
          role="note"
          aria-label="About outcome assessments"
          className="flex gap-2 rounded-md bg-brand-50 px-3 py-2 text-xs leading-relaxed text-brand-700 ring-1 ring-inset ring-brand-200"
        >
          <Scale className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <span>
            Decision support, not a prediction and not legal advice. An assessment uses only the
            findings a lawyer accepted in this analysis and the judgment passages behind the
            accepted precedent comparisons. Its uncertainty is a category, never a probability. It
            counts as a lawyer&apos;s view only once a reviewer accepts it.
          </span>
        </div>

        {list.isPending && (
          <p role="status" className="text-xs text-brand-500">
            Loading assessments…
          </p>
        )}
        {list.isError && (
          <div role="alert" className={alertClass}>
            The assessments could not be loaded: {errorMessage(list.error)}{' '}
            <button
              type="button"
              className="font-medium underline underline-offset-2"
              onClick={() => void list.refetch()}
            >
              Try again
            </button>
          </div>
        )}
        {list.data && (
          <>
            <div className="flex flex-col gap-3 rounded-lg border border-brand-100 bg-brand-50/40 p-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-xs leading-relaxed text-brand-600">
                Uses {list.data.acceptedFindings} accepted{' '}
                {list.data.acceptedFindings === 1 ? 'finding' : 'findings'} and{' '}
                {list.data.acceptedPrecedents} accepted precedent{' '}
                {list.data.acceptedPrecedents === 1 ? 'comparison' : 'comparisons'}. Unreviewed and
                rejected findings and reviewers&apos; notes are never used.
              </p>
              <Button
                size="sm"
                className="shrink-0 self-start sm:self-auto"
                onClick={() => generate.mutate(undefined, { onSuccess: (a) => setSelected(a.id) })}
                disabled={!list.data.canGenerate || generate.isPending}
                aria-describedby={list.data.canGenerate ? undefined : reasonId}
              >
                {generate.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Scale className="h-4 w-4" aria-hidden="true" />
                )}
                {generate.isPending ? 'Assessing…' : 'Generate assessment'}
              </Button>
            </div>
            {!list.data.canGenerate && list.data.cannotGenerateReason && (
              <p
                id={reasonId}
                role="status"
                className="flex gap-2 rounded-md bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-900 ring-1 ring-inset ring-amber-600/30"
              >
                <Info className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                <span>
                  <span className="font-semibold">Why no assessment can be generated: </span>
                  {list.data.cannotGenerateReason}
                </span>
              </p>
            )}
            {generate.isError && (
              <p role="alert" className={alertClass}>
                No assessment was generated. {errorMessage(generate.error)}
              </p>
            )}
            {items.length === 0 ? (
              <p className="text-xs text-brand-500">No assessment of this analysis yet.</p>
            ) : (
              shown && (
                <AssessmentView
                  caseId={caseId}
                  runId={runId}
                  assessment={shown}
                  canReview={list.data.canReview}
                />
              )
            )}
            {items.length > 1 && (
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-brand-400">
                  Earlier assessments
                </p>
                <ul className="mt-1 divide-y divide-brand-100 rounded-md border border-brand-100">
                  {items.map((a) => (
                    <li key={a.id}>
                      <button
                        type="button"
                        aria-current={a.id === shown?.id ? 'true' : undefined}
                        onClick={() => setSelected(a.id)}
                        className={`flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left text-xs hover:bg-brand-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-500 ${a.id === shown?.id ? 'bg-brand-50' : ''}`}
                      >
                        <span>{when(a.createdAt)}</span>
                        <span className="flex items-center gap-1.5">
                          <StatusChip assessment={a} />
                          {a.status === 'ready' && <ReviewStatusBadge status={a.review.status} />}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </CardBody>
    </Card>
  );
}

function StatusChip({ assessment: a }: { assessment: Assessment }) {
  if (a.status === 'ready')
    return <Chip label="Assessment" className={STANCE.supports.className} />;
  if (a.status === 'insufficient')
    return <Chip label="No basis" className={UNCERTAINTY.insufficient_basis.className} />;
  return <Chip label="Failed" className={STANCE.cuts_against.className} />;
}

function AssessmentView({
  caseId,
  runId,
  assessment: a,
  canReview,
}: {
  caseId: string;
  runId: string;
  assessment: Assessment;
  canReview: boolean;
}) {
  return (
    <section
      aria-label={`Assessment of ${when(a.createdAt)}`}
      className="space-y-3 rounded-lg border border-brand-100 bg-white p-4"
    >
      <p className="text-xs text-brand-500">
        {a.providerLabel ?? a.provider} · model {a.model} · {a.promptVersion}
        {a.validatorVersion && ` · checked by ${a.validatorVersion}`} · {when(a.createdAt)}
        {a.requestedBy && ` · by ${a.requestedBy.name}`}
      </p>
      {a.inputsChanged && (
        <p
          role="status"
          className="flex gap-2 rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-900 ring-1 ring-inset ring-amber-600/30"
        >
          <AlertTriangle className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          The accepted findings or a precedent passage changed after this assessment. Generate a new
          assessment to use the current review.
        </p>
      )}
      {a.status === 'failed' && (
        <p role="alert" className={alertClass}>
          The assessment failed: {a.reason ?? 'no reason was recorded.'} Nothing from it is shown.
          Generate a new assessment to try again.
        </p>
      )}
      {a.status === 'insufficient' && (
        <p className="rounded-md bg-brand-50 px-3 py-2 text-brand-800 ring-1 ring-inset ring-brand-200">
          <strong>No assessment: insufficient basis.</strong> {a.reason}
        </p>
      )}
      {a.status === 'ready' && a.result && <AssessmentResultView result={a.result} />}
      {a.removed && a.removed.count > 0 && (
        <div className="rounded-md bg-brand-50 px-3 py-2 ring-1 ring-inset ring-brand-200">
          <p className="text-xs font-medium text-brand-800">
            {a.removed.count} {a.removed.count === 1 ? 'item was' : 'items were'} removed by the
            server&apos;s checks:
          </p>
          <ul className="mt-1 list-disc pl-5 text-xs text-brand-600">
            {a.removed.reasons.map((r) => (
              <li key={r.code}>
                {r.message} ({r.count})
              </li>
            ))}
          </ul>
        </div>
      )}
      {a.status === 'ready' && a.result && (
        <AssessmentReviewControls
          caseId={caseId}
          runId={runId}
          assessment={a}
          summary={a.result.summary}
          canReview={canReview}
        />
      )}
    </section>
  );
}

function AssessmentResultView({ result: r }: { result: AssessmentResult }) {
  return (
    <div className="space-y-3">
      {r.demoOnly && (
        <p
          role="note"
          aria-label="Demonstration on synthetic data"
          className="flex gap-2 rounded-md bg-amber-50 px-3 py-2 text-xs font-medium text-amber-900 ring-1 ring-inset ring-amber-600/30"
        >
          <FlaskConical className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          Demonstration only: produced from SYNTHETIC test judgments (fictional, not real law)
          and/or by the scripted test provider (not AI). It says nothing about how a real court
          would decide.
        </p>
      )}
      <div className="rounded-lg bg-brand-900 px-5 py-4 text-white">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-brand-300">
            Uncertainty
          </span>
          <Chip {...UNCERTAINTY[r.uncertainty]} />
          <span className="text-xs text-brand-300">(a category, not a probability)</span>
        </div>
        <p className="mt-2.5 max-w-[70ch] font-serif text-[15px] leading-relaxed text-white">
          {r.summary}
        </p>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_17rem]">
        <div>
          <h4 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-brand-500">
            Reasoning
          </h4>
          <ol className="mt-2 space-y-2.5 text-sm text-brand-800">
            {r.reasoning.map((step, index) => (
              <li key={step.id} className="flex gap-3">
                <span className="mt-px font-semibold tabular-nums text-accent-600">
                  {index + 1}.
                </span>
                <span>
                  {step.text}{' '}
                  <span className="text-xs text-brand-500">
                    (rests on {[...step.findingIds, ...step.precedentRefs].join(', ')})
                  </span>
                </span>
              </li>
            ))}
          </ol>
        </div>
        <div className="space-y-4">
          {[
            {
              title: 'Missing evidence',
              points: r.missingEvidence,
              tone: 'bg-amber-50 text-amber-950',
            },
            { title: 'Limitations', points: r.limitations, tone: 'bg-canvas text-brand-800' },
          ].map(
            ({ title, points, tone }) =>
              points.length > 0 && (
                <div key={title} className={`rounded-md px-4 py-3 ${tone}`}>
                  <h4 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-brand-500">
                    {title}
                  </h4>
                  <ul className="mt-1.5 list-disc space-y-1 pl-4 text-sm">
                    {points.map((point, i) => (
                      <li key={`${i}-${point}`}>{point}</li>
                    ))}
                  </ul>
                </div>
              ),
          )}
        </div>
      </div>

      <div>
        <h4 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-brand-500">
          Precedents relied on ({r.precedents.length})
        </h4>
        <ul className="mt-1 divide-y divide-brand-100">
          {r.precedents.map((p) => (
            <li key={p.ref} className="py-3.5">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-semibold text-brand-900">
                    <span className="mr-2 inline-block rounded bg-brand-900 px-1.5 py-px align-[1px] text-[11px] font-semibold text-white">
                      {p.ref}
                    </span>
                    {p.title}
                  </p>
                  <p className="mt-0.5 text-xs text-brand-500">
                    {[p.citation, p.court, p.year].filter(Boolean).join(' · ')}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-1.5">
                  {p.synthetic && <SyntheticBadge />}
                  <Chip {...STANCE[p.stance]} />
                </div>
              </div>
              <blockquote className="mt-2 rounded-md bg-canvas px-3 py-2 font-serif text-[13px] leading-relaxed text-brand-700">
                &ldquo;{p.quote}&rdquo;
              </blockquote>
              <p className="mt-2 text-sm text-brand-800">{p.explanation}</p>
              <Link
                to={judgmentPath(p.judgmentId, p.passage.sectionNumber)}
                className="mt-1.5 inline-flex items-center gap-1 text-xs font-semibold text-brand-800 underline-offset-2 hover:underline"
              >
                <BookOpen className="h-3.5 w-3.5 text-accent-600" aria-hidden="true" />
                Read the passage ({place(p.passage.pageNumber, p.passage.sectionNumber)})
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

type Mode = 'idle' | 'edit' | 'reject' | 'clear';

function AssessmentReviewControls({
  caseId,
  runId,
  assessment: a,
  summary,
  canReview,
}: {
  caseId: string;
  runId: string;
  assessment: Assessment;
  summary: string;
  canReview: boolean;
}) {
  const review = a.review;
  const [mode, setMode] = useState<Mode>('idle');
  const [text, setText] = useState('');
  const [note, setNote] = useState('');
  const [showHistory, setShowHistory] = useState(false);
  const mutation = useReviewAssessment(caseId, runId);
  const textId = useId();
  const noteId = useId();
  const busy = mutation.isPending;

  const open = (next: Mode) => {
    mutation.reset();
    setText(review.reviewedText ?? summary);
    setNote(review.note ?? '');
    setMode(next);
  };
  const submit = (input: Omit<AssessmentReviewInput, 'expectedVersion'>) =>
    mutation.mutate(
      { assessmentId: a.id, input: { ...input, expectedVersion: review.version } },
      { onSuccess: () => setMode('idle') },
    );

  return (
    <section
      aria-label="Lawyer review of this assessment"
      className="rounded-md border border-brand-200 bg-white px-3 py-2"
    >
      <div className="flex flex-wrap items-center gap-2">
        <ReviewStatusBadge status={review.status} />
        {review.reviewedAt && (
          <span className="text-xs text-brand-500">
            {review.reviewedBy && `by ${review.reviewedBy.name} · `}
            {when(review.reviewedAt)}
          </span>
        )}
        {review.status === 'unreviewed' && (
          <span className="text-xs text-brand-500">
            Not yet reviewed: this is not a lawyer&apos;s view and is not in the case brief.
          </span>
        )}
        {(review.status === 'accepted' || review.status === 'edited') && (
          <span className="text-xs text-brand-500">
            The case brief includes it in its own section, labelled as decision support.
          </span>
        )}
      </div>
      {review.status === 'edited' && review.reviewedText && (
        <p className="mt-1.5 text-brand-900">
          <span className="font-medium">Lawyer’s wording of the summary: </span>
          {review.reviewedText}
          <span className="block text-xs text-brand-500">The original summary is kept above.</span>
        </p>
      )}
      {review.note && (
        <p className="mt-1 text-xs text-brand-600">
          <span className="font-medium">Reviewer&apos;s note (not in the brief): </span>
          {review.note}
        </p>
      )}

      {canReview && mode === 'idle' && (
        <div className="mt-2 flex flex-wrap gap-2">
          {review.status !== 'accepted' && (
            <Button size="sm" disabled={busy} onClick={() => submit({ status: 'accepted' })}>
              Accept assessment
            </Button>
          )}
          <Button size="sm" variant="secondary" disabled={busy} onClick={() => open('edit')}>
            Edit summary
          </Button>
          {review.status !== 'rejected' && (
            <Button size="sm" variant="secondary" disabled={busy} onClick={() => open('reject')}>
              Reject
            </Button>
          )}
          {review.status !== 'unreviewed' && (
            <Button size="sm" variant="ghost" disabled={busy} onClick={() => open('clear')}>
              Clear decision
            </Button>
          )}
        </div>
      )}

      {canReview && mode === 'edit' && (
        <form
          className="mt-2 space-y-2"
          onSubmit={(e) => {
            e.preventDefault();
            submit({ status: 'edited', reviewedText: text, note: note || null });
          }}
        >
          <label className="label-text" htmlFor={textId}>
            Lawyer’s wording of the summary
          </label>
          <textarea
            id={textId}
            className="input-field min-h-[70px] resize-y"
            maxLength={2000}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <label className="label-text" htmlFor={noteId}>
            Note (optional; seen by reviewers only, never in the brief)
          </label>
          <textarea
            id={noteId}
            className="input-field min-h-[50px] resize-y"
            maxLength={2000}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <div className="flex gap-2">
            <Button size="sm" type="submit" disabled={busy || !text.trim()}>
              Save wording
            </Button>
            <Button size="sm" variant="ghost" disabled={busy} onClick={() => setMode('idle')}>
              Cancel
            </Button>
          </div>
        </form>
      )}

      {canReview && mode === 'reject' && (
        <form
          className="mt-2 space-y-2"
          onSubmit={(e) => {
            e.preventDefault();
            submit({ status: 'rejected', note: note || null });
          }}
        >
          <label className="label-text" htmlFor={noteId}>
            Reason for rejecting the assessment (optional; seen by reviewers only)
          </label>
          <textarea
            id={noteId}
            className="input-field min-h-[50px] resize-y"
            maxLength={2000}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <div className="flex gap-2">
            <Button size="sm" variant="danger" type="submit" disabled={busy}>
              Reject assessment
            </Button>
            <Button size="sm" variant="ghost" disabled={busy} onClick={() => setMode('idle')}>
              Cancel
            </Button>
          </div>
        </form>
      )}

      {canReview && mode === 'clear' && (
        <div className="mt-2 space-y-2">
          <p className="text-xs text-brand-700">
            Return the assessment to unreviewed? The history keeps this decision.
          </p>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="secondary"
              disabled={busy}
              onClick={() => submit({ status: 'unreviewed', note: review.note })}
            >
              Clear decision
            </Button>
            <Button size="sm" variant="ghost" disabled={busy} onClick={() => setMode('idle')}>
              Cancel
            </Button>
          </div>
        </div>
      )}

      {busy && (
        <p role="status" className="mt-1 text-xs text-brand-500">
          Saving…
        </p>
      )}
      {mutation.isError && (
        <p role="alert" className="mt-1 text-xs text-red-700">
          {errorMessage(mutation.error)}
        </p>
      )}
      {review.version > 0 && (
        <button
          type="button"
          className="mt-1.5 text-xs font-medium text-brand-700 underline-offset-2 hover:underline"
          aria-expanded={showHistory}
          onClick={() => setShowHistory((v) => !v)}
        >
          {showHistory ? 'Hide history' : 'Show history'}
        </button>
      )}
      {showHistory && <AssessmentHistory caseId={caseId} runId={runId} assessmentId={a.id} />}
    </section>
  );
}

const VERB: Record<string, string> = {
  unreviewed: 'Returned to unreviewed',
  accepted: 'Accepted',
  edited: 'Accepted with edits',
  rejected: 'Rejected',
};

function AssessmentHistory({
  caseId,
  runId,
  assessmentId,
}: {
  caseId: string;
  runId: string;
  assessmentId: string;
}) {
  const history = useAssessmentHistory(caseId, runId, assessmentId, true);
  if (history.isPending) return <p className="mt-1 text-xs text-brand-500">Loading history…</p>;
  if (history.isError)
    return (
      <p role="alert" className="mt-1 text-xs text-red-700">
        {errorMessage(history.error)}
      </p>
    );
  return (
    <ol
      aria-label="History of the assessment review"
      className="mt-1 space-y-1 text-xs text-brand-600"
    >
      {history.data.items.map((entry) => (
        <li key={entry.version}>
          <span className="font-medium">
            {VERB[entry.status]}
            {entry.actor && ` by ${entry.actor.name}`}
          </span>{' '}
          · {when(entry.occurredAt)}
          {entry.reviewedText && <span className="block">Wording: {entry.reviewedText}</span>}
          {entry.note && <span className="block">Note: {entry.note}</span>}
        </li>
      ))}
    </ol>
  );
}
