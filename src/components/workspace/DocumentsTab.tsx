import { useRef, useState, type DragEvent } from 'react';
import { ExternalLink, FileText, Loader2, Share2, Trash2, UploadCloud } from 'lucide-react';
import type { Case, CaseDocument } from '../../types';
import { useDeleteDocument, useShareDocument, useUploadDocument } from '../../hooks/useCases';
import { ApiError, errorMessage } from '../../services/api/client';
import { documentDownloadUrl } from '../../services/api/lexflow';
import { Card, CardBody, CardHeader } from '../ui/Card';
import { Button } from '../ui/Button';
import { formatDate } from '../../lib/format';
import { DeletedDocumentsCard } from './DeletedDocumentsCard';
import {
  ACCEPT_ATTRIBUTE,
  ACCEPTED_TYPES_LABEL,
  REJECTION_MESSAGES,
  checkFiles,
} from '../../lib/documentFiles';

interface Rejection {
  name: string;
  message: string;
}

interface UploadFeedback {
  added: string[];
  rejected: Rejection[];
}

interface Progress {
  current: string;
  index: number;
  total: number;
}

/**
 * A failure message that says which file it is about. Some server messages
 * name the file ("X is empty."), others don't ("This file is larger than the
 * 25 MB upload limit.", "Can't reach the LexFlow server…").
 */
function withFileName(name: string, error: unknown): string {
  const message = errorMessage(error);
  return message.includes(name) ? message : `${name}: ${message}`;
}

export function DocumentsTab({ legalCase: c }: { legalCase: Case }) {
  const upload = useUploadDocument(c.id);
  const remove = useDeleteDocument(c.id);
  const share = useShareDocument(c.id);
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [feedback, setFeedback] = useState<UploadFeedback | null>(null);
  const [removing, setRemoving] = useState<ReadonlySet<string>>(new Set());
  // Why each failed removal failed, by document id.
  const [removeErrors, setRemoveErrors] = useState<ReadonlyMap<string, string>>(new Map());
  const [busyNotice, setBusyNotice] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const busy = progress !== null;

  // Picker and drag-and-drop both end here, so they follow the same rules.
  const attach = async (fileList: FileList | null) => {
    const files = fileList ? Array.from(fileList) : [];
    if (files.length === 0) return; // cancelled picker, or a drag with no files
    if (busy) {
      // Only drops can arrive now (the button is disabled); say so rather
      // than dropping the files silently.
      const what = files.length === 1 ? files[0].name : `these ${files.length} files`;
      setBusyNotice(`${what} not added: wait for the current upload to finish, then add again.`);
      return;
    }
    setBusyNotice(null);

    // Quick checks in the browser first; the server checks everything again.
    const { accepted, rejected } = checkFiles(
      files,
      c.documents.map((d) => d.name),
    );
    const result: UploadFeedback = {
      added: [],
      rejected: rejected.map((r) => ({
        name: r.name,
        message: `${r.name} ${REJECTION_MESSAGES[r.reason]}`,
      })),
    };
    setFeedback(null);

    // One request per file, so one rejected file never blocks the others.
    for (const [index, file] of accepted.entries()) {
      setProgress({ current: file.name, index: index + 1, total: accepted.length });
      try {
        await upload.mutateAsync(file);
        result.added.push(file.name);
      } catch (error) {
        result.rejected.push({ name: file.name, message: withFileName(file.name, error) });
      }
    }
    setProgress(null);
    setFeedback(result);
  };

  const setRemoveError = (id: string, message: string | null) =>
    setRemoveErrors((prev) => {
      const next = new Map(prev);
      if (message === null) next.delete(id);
      else next.set(id, message);
      return next;
    });

  // Each removal settles through its own promise. (Callbacks passed to
  // `mutate()` only fire for the latest call, so two removals in flight at
  // once would lose the first one's outcome.)
  const removeDocument = async (doc: CaseDocument) => {
    setRemoveError(doc.id, null);
    setNotice(null);
    setRemoving((prev) => new Set(prev).add(doc.id));
    try {
      await remove.mutateAsync(doc.id);
      setNotice(
        c.permissions.canRestoreDocuments
          ? `Removed ${doc.name}. It can be restored from Deleted Documents below.`
          : `Removed ${doc.name}.`,
      );
    } catch (error) {
      // Already removed elsewhere (another tab, say): the goal is met.
      const alreadyGone = error instanceof ApiError && error.code === 'document-not-found';
      if (!alreadyGone) {
        setRemoveError(doc.id, `${doc.name} was not removed. ${errorMessage(error)}`);
      }
    } finally {
      setRemoving((prev) => {
        const next = new Set(prev);
        next.delete(doc.id);
        return next;
      });
    }
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    void attach(e.dataTransfer.files);
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    // Moving over a child element fires dragleave too; only reset when the
    // pointer actually leaves the drop zone.
    if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDragging(false);
  };

  const { canUploadDocuments, canDeleteDocuments, canShareDocuments } = c.permissions;

  const toggleShared = (doc: CaseDocument) => {
    setNotice(null);
    const sharing = doc.sharedWithClientAt === null;
    share.mutate(
      { id: doc.id, share: sharing },
      {
        onSuccess: () =>
          setNotice(
            sharing
              ? `Shared ${doc.name} with the client: it is now in their portal.`
              : `Stopped sharing ${doc.name}: it has left the client's portal.`,
          ),
        onError: (error) =>
          setRemoveError(doc.id, `${doc.name}: sharing was not changed. ${errorMessage(error)}`),
      },
    );
  };

  return (
    <div className="space-y-6">
      {!canUploadDocuments && (
        <p className="text-sm text-brand-500">You can open this case's documents.</p>
      )}
      <div
        hidden={!canUploadDocuments}
        data-testid="document-drop-zone"
        onDragOver={(e) => {
          // Accept drops even while uploading (no dropEffect 'none', which
          // would make the browser skip the drop event): attach() then says
          // why the files were not added instead of ignoring them silently.
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        aria-busy={busy}
        className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 text-center transition ${
          dragging ? 'border-brand-500 bg-brand-50' : 'border-brand-200 bg-white'
        }`}
      >
        <UploadCloud className="h-9 w-9 text-brand-300" strokeWidth={1.5} aria-hidden="true" />
        <p className="mt-3 text-sm font-medium text-brand-800">
          Drop pleadings, evidence, orders or correspondence here
        </p>
        <p className="mt-1 text-xs text-brand-500">{ACCEPTED_TYPES_LABEL}</p>
        <Button
          variant="secondary"
          size="sm"
          className="mt-4"
          disabled={busy}
          onClick={() => inputRef.current?.click()}
        >
          Choose files
        </Button>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPT_ATTRIBUTE}
          className="hidden"
          aria-label="Choose files to attach"
          onChange={(e) => {
            void attach(e.target.files);
            e.target.value = '';
          }}
        />
        <p className="mt-4 max-w-md text-xs text-brand-400">
          Files are stored by the LexFlow server on this computer and stay available after a
          refresh. Each file&apos;s contents are checked against its type before it is saved.
        </p>
      </div>

      <div role="status" aria-live="polite">
        {progress && (
          <p className="flex items-center gap-2 text-sm text-brand-600">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            Uploading {progress.current}
            {progress.total > 1 && ` (${progress.index} of ${progress.total})`}…
          </p>
        )}
        {busyNotice && (
          <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800 ring-1 ring-inset ring-amber-600/20">
            {busyNotice}
          </p>
        )}
        {feedback && <UploadSummary feedback={feedback} />}
        {notice && (
          <p className="rounded-md bg-brand-50 px-3 py-2 text-sm text-brand-800 ring-1 ring-inset ring-brand-600/20">
            {notice}
          </p>
        )}
      </div>

      {removeErrors.size > 0 && (
        <div
          role="alert"
          className="space-y-1 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-inset ring-red-600/20"
        >
          {[...removeErrors].map(([id, message]) => (
            <p key={id}>{message}</p>
          ))}
        </div>
      )}

      <Card>
        <CardHeader title={`Case Documents (${c.documents.length})`} />
        <CardBody className="p-0">
          {c.documents.length === 0 ? (
            <p className="px-5 py-6 text-sm text-brand-500">
              No documents yet. Upload the case papers to prepare this matter for analysis.
            </p>
          ) : (
            <ul className="divide-y divide-brand-100" aria-label="Case documents">
              {c.documents.map((doc) => {
                const isRemoving = removing.has(doc.id);
                return (
                  <li key={doc.id} className="flex items-center gap-3 px-5 py-3">
                    <span className="rounded-md bg-brand-50 p-2 text-brand-500">
                      <FileText className="h-4 w-4" aria-hidden="true" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-brand-900">{doc.name}</p>
                      <p className="text-xs text-brand-500">
                        {doc.type} · {doc.size} · {formatDate(doc.uploadedOn)}
                        {doc.uploadedBy && ` · added by ${doc.uploadedBy.name}`}
                        {!doc.hasFile && ' · sample record, no file attached'}
                      </p>
                      {doc.sharedWithClientAt && (
                        <p className="mt-0.5 text-xs font-medium text-accent-600">
                          Shared with client
                        </p>
                      )}
                    </div>
                    {doc.hasFile && (
                      <a
                        href={documentDownloadUrl(doc.id)}
                        target="_blank"
                        rel="noreferrer"
                        className="rounded-md p-2 text-brand-500 hover:bg-brand-50 hover:text-brand-800"
                        aria-label={`Open ${doc.name}`}
                        title="Open"
                      >
                        <ExternalLink className="h-4 w-4" aria-hidden="true" />
                      </a>
                    )}
                    {canShareDocuments && doc.hasFile && (
                      <button
                        type="button"
                        onClick={() => toggleShared(doc)}
                        disabled={share.isPending}
                        aria-pressed={doc.sharedWithClientAt !== null}
                        className="rounded-md p-2 text-brand-400 hover:bg-brand-50 hover:text-brand-800 disabled:opacity-60 aria-pressed:text-accent-600"
                        aria-label={
                          doc.sharedWithClientAt
                            ? `Stop sharing ${doc.name} with the client`
                            : `Share ${doc.name} with the client`
                        }
                        title={
                          doc.sharedWithClientAt ? 'Stop sharing with client' : 'Share with client'
                        }
                      >
                        <Share2 className="h-4 w-4" aria-hidden="true" />
                      </button>
                    )}
                    {canDeleteDocuments && (
                      <button
                        type="button"
                        onClick={() => void removeDocument(doc)}
                        disabled={isRemoving}
                        className="rounded-md p-2 text-brand-400 hover:bg-red-50 hover:text-red-600 disabled:cursor-wait disabled:opacity-60"
                        aria-label={isRemoving ? `Removing ${doc.name}` : `Remove ${doc.name}`}
                        title={isRemoving ? 'Removing…' : 'Remove'}
                      >
                        {isRemoving ? (
                          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                        ) : (
                          <Trash2 className="h-4 w-4" aria-hidden="true" />
                        )}
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </CardBody>
      </Card>

      {c.permissions.canRestoreDocuments && <DeletedDocumentsCard caseId={c.id} />}
    </div>
  );
}

function UploadSummary({ feedback }: { feedback: UploadFeedback }) {
  const { added, rejected } = feedback;
  return (
    <div className="space-y-2">
      {added.length > 0 && (
        <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-800 ring-1 ring-inset ring-emerald-600/20">
          {added.length === 1 ? `Added ${added[0]}.` : `Added ${added.length} documents.`}
        </p>
      )}
      {rejected.length > 0 && (
        <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-inset ring-red-600/20">
          <p className="font-medium">
            {rejected.length === 1
              ? 'One file was not added:'
              : `${rejected.length} files were not added:`}
          </p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5">
            {rejected.map((r, i) => (
              <li key={`${i}-${r.name}`}>{r.message}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
