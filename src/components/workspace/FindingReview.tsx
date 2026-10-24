import { useId, useState } from 'react';
import { useExportBrief, useReviewFinding, useReviewHistory } from '../../hooks/useFindingReviews';
import { saveFile } from '../../lib/saveFile';
import { errorMessage } from '../../services/api/client';
import { formatDate, formatTime } from '../../lib/format';
import type {
  AnalysisReview,
  AnalysisReviewInput,
  AnalysisReviewSummary,
  ReviewStatus,
} from '../../types/ai';
import { Button } from '../ui/Button';

/**
 * Lawyer review of one AI finding (Phase 6). The model's wording stays on
 * screen as the AI's; a decision is shown only once the server has stored it.
 */

const when = (iso: string) => `${formatDate(iso.slice(0, 10))}, ${formatTime(iso)}`;

const STATUS: Record<ReviewStatus, { label: string; className: string; verb: string }> = {
  unreviewed: {
    label: 'Unreviewed',
    className: 'bg-amber-50 text-amber-800 ring-amber-600/30',
    verb: 'Returned to unreviewed',
  },
  accepted: {
    label: 'Accepted',
    className: 'bg-emerald-50 text-emerald-800 ring-emerald-600/30',
    verb: 'Accepted',
  },
  edited: {
    label: 'Edited by lawyer',
    className: 'bg-sky-50 text-sky-800 ring-sky-600/30',
    verb: 'Accepted with edits',
  },
  rejected: {
    label: 'Rejected',
    className: 'bg-red-50 text-red-800 ring-red-600/30',
    verb: 'Rejected',
  },
};

export function ReviewStatusBadge({ status }: { status: ReviewStatus }) {
  const { label, className } = STATUS[status];
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${className}`}
    >
      {label}
    </span>
  );
}

/** How far the review of a run has got; never says "approved" while anything is open. */
export function ReviewProgress({ summary }: { summary: AnalysisReviewSummary }) {
  const reviewed = summary.total - summary.unreviewed;
  return (
    <div className="rounded-md bg-brand-50 px-3 py-2 text-sm text-brand-800 ring-1 ring-inset ring-brand-200">
      <p className="font-medium">
        Lawyer review: {reviewed} of {summary.total} {summary.total === 1 ? 'finding' : 'findings'}{' '}
        reviewed
      </p>
      <p className="text-xs text-brand-600">
        {summary.accepted} accepted, {summary.edited} accepted with edits, {summary.rejected}{' '}
        rejected, {summary.unreviewed} unreviewed.
        {summary.unreviewed > 0 &&
          ' Unreviewed findings are the AI’s, not yet checked by a lawyer.'}
      </p>
    </div>
  );
}

/**
 * The case brief (DOCX) made by the server from the accepted findings only.
 * Anyone who can see the analysis may export it; it needs one accepted finding.
 */
export function ExportBrief({
  caseId,
  runId,
  summary,
}: {
  caseId: string;
  runId: string;
  summary: AnalysisReviewSummary;
}) {
  const exportBrief = useExportBrief(caseId, runId);
  const [saved, setSaved] = useState<string | null>(null);
  const included = summary.accepted + summary.edited;
  const hintId = useId();
  return (
    <div className="space-y-1">
      <Button
        size="sm"
        variant="secondary"
        disabled={included === 0 || exportBrief.isPending}
        aria-describedby={hintId}
        onClick={() => {
          setSaved(null);
          exportBrief.mutate(undefined, {
            onSuccess: (file) => {
              saveFile(file);
              setSaved(file.filename);
            },
          });
        }}
      >
        {exportBrief.isPending ? 'Preparing the brief…' : 'Export case brief (DOCX)'}
      </Button>
      <p id={hintId} className="text-xs text-brand-500">
        {included === 0
          ? 'Accept at least one finding first: the brief contains only accepted findings.'
          : `The brief will contain the ${included} accepted ${included === 1 ? 'finding' : 'findings'} with their sources; unreviewed and rejected findings are left out, and reviewers’ notes are never included.`}
      </p>
      {saved && (
        <p role="status" className="text-xs text-emerald-800">
          Brief saved as {saved}.
        </p>
      )}
      {exportBrief.isError && (
        <p role="alert" className="text-xs text-red-700">
          {errorMessage(exportBrief.error)}
        </p>
      )}
    </div>
  );
}

type Mode = 'idle' | 'edit' | 'reject' | 'clear';

export function FindingReview({
  caseId,
  runId,
  label,
  originalText,
  review,
  canReview,
  sourceChanged = false,
}: {
  caseId: string;
  runId: string;
  label: string;
  originalText: string;
  review: AnalysisReview;
  canReview: boolean;
  sourceChanged?: boolean;
}) {
  const [mode, setMode] = useState<Mode>('idle');
  const [text, setText] = useState('');
  const [note, setNote] = useState('');
  const [showHistory, setShowHistory] = useState(false);
  const mutation = useReviewFinding(caseId, runId);
  const textId = useId();
  const noteId = useId();

  const open = (next: Mode) => {
    mutation.reset();
    setText(review.reviewedText ?? originalText);
    setNote(review.note ?? '');
    setMode(next);
  };
  const submit = (input: Omit<AnalysisReviewInput, 'expectedVersion'>) =>
    mutation.mutate(
      { findingId: review.findingId, input: { ...input, expectedVersion: review.version } },
      { onSuccess: () => setMode('idle') },
    );
  const busy = mutation.isPending;
  const { verb } = STATUS[review.status];

  return (
    <section
      aria-label={`Review of ${label}`}
      className="mt-2 rounded-md border border-brand-200 bg-white px-3 py-2 text-sm"
    >
      <div className="flex flex-wrap items-center gap-2">
        <ReviewStatusBadge status={review.status} />
        {review.reviewedAt && (
          <span className="text-xs text-brand-500">
            {verb}
            {review.reviewedBy && ` by ${review.reviewedBy.name}`} · {when(review.reviewedAt)}
          </span>
        )}
      </div>
      {review.status === 'edited' && review.reviewedText && (
        <p className="mt-1.5 text-brand-900">
          <span className="font-medium">Lawyer’s wording: </span>
          {review.reviewedText}
          <span className="block text-xs text-brand-500">
            The AI’s original wording is kept and shown above.
          </span>
        </p>
      )}
      {review.note && (
        <p className="mt-1 text-xs text-brand-600">
          <span className="font-medium">Reviewer’s note (not in the brief): </span>
          {review.note}
        </p>
      )}
      {sourceChanged && (
        <p className="mt-1 text-xs font-medium text-amber-800">
          A source of this finding changed after the analysis ran. Check it before accepting.
        </p>
      )}

      {canReview && mode === 'idle' && (
        <div className="mt-2 flex flex-wrap gap-2">
          {review.status !== 'accepted' && (
            <Button size="sm" disabled={busy} onClick={() => submit({ status: 'accepted' })}>
              Accept
            </Button>
          )}
          <Button size="sm" variant="secondary" disabled={busy} onClick={() => open('edit')}>
            Edit wording
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
            Lawyer’s wording for {label}
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
            Reason for rejecting {label} (optional; seen by reviewers only)
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
              Reject finding
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
            Return {label} to unreviewed? The history keeps this decision.
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
      {showHistory && <ReviewHistory caseId={caseId} runId={runId} findingId={review.findingId} />}
    </section>
  );
}

function ReviewHistory({
  caseId,
  runId,
  findingId,
}: {
  caseId: string;
  runId: string;
  findingId: string;
}) {
  const history = useReviewHistory(caseId, runId, findingId, true);
  if (history.isPending) return <p className="mt-1 text-xs text-brand-500">Loading history…</p>;
  if (history.isError)
    return (
      <p role="alert" className="mt-1 text-xs text-red-700">
        {errorMessage(history.error)}
      </p>
    );
  return (
    <ol aria-label={`History of ${findingId}`} className="mt-1 space-y-1 text-xs text-brand-600">
      {history.data.items.map((entry) => (
        <li key={entry.version}>
          <span className="font-medium">
            {STATUS[entry.status].verb}
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
