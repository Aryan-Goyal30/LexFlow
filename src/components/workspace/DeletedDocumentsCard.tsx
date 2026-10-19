import { useState } from 'react';
import { ArchiveRestore, FileText, Loader2 } from 'lucide-react';
import type { DeletedDocument } from '../../types';
import { useDeletedDocuments, useRestoreDocument } from '../../hooks/useCases';
import { errorMessage } from '../../services/api/client';
import { Card, CardBody, CardHeader } from '../ui/Card';
import { Button } from '../ui/Button';
import { formatDate } from '../../lib/format';

/**
 * Documents removed from the case, kept until someone restores them (the
 * Administrator or the lead advocate). Only an operator can purge them for
 * good, from the command line; nothing is purged automatically.
 */
export function DeletedDocumentsCard({ caseId }: { caseId: string }) {
  const deleted = useDeletedDocuments(caseId);
  const restore = useRestoreDocument(caseId);
  const [restoring, setRestoring] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<{ ok: boolean; message: string } | null>(null);

  const restoreOne = async (doc: DeletedDocument) => {
    setOutcome(null);
    setRestoring(doc.id);
    try {
      await restore.mutateAsync(doc.id);
      setOutcome({ ok: true, message: `Restored ${doc.name}.` });
    } catch (error) {
      setOutcome({ ok: false, message: `${doc.name} was not restored. ${errorMessage(error)}` });
    } finally {
      setRestoring(null);
    }
  };

  const count = deleted.data?.length;
  return (
    <Card>
      <CardHeader
        title={count === undefined ? 'Deleted Documents' : `Deleted Documents (${count})`}
      />
      <CardBody className="space-y-3">
        <p className="text-xs text-brand-500">
          Deleted documents are kept, with their files, until restored here. Only an operator can
          remove them permanently.
        </p>
        <div aria-live="polite">
          {outcome && (
            <p
              role={outcome.ok ? 'status' : 'alert'}
              className={`rounded-md px-3 py-2 text-sm ring-1 ring-inset ${
                outcome.ok
                  ? 'bg-emerald-50 text-emerald-800 ring-emerald-600/20'
                  : 'bg-red-50 text-red-700 ring-red-600/20'
              }`}
            >
              {outcome.message}
            </p>
          )}
        </div>
        {deleted.isPending ? (
          <p className="text-sm text-brand-500">Loading deleted documents…</p>
        ) : deleted.isError ? (
          <p role="alert" className="text-sm text-red-600">
            Couldn't load the deleted documents. {errorMessage(deleted.error)}
          </p>
        ) : deleted.data.length === 0 ? (
          <p className="text-sm text-brand-500">No deleted documents.</p>
        ) : (
          <ul className="divide-y divide-brand-100" aria-label="Deleted documents">
            {deleted.data.map((doc) => (
              <li key={doc.id} className="flex items-center gap-3 py-3">
                <span className="rounded-md bg-brand-50 p-2 text-brand-400">
                  <FileText className="h-4 w-4" aria-hidden="true" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm text-brand-700">{doc.name}</p>
                  <p className="text-xs text-brand-500">
                    Deleted {formatDate(doc.deletedAt.slice(0, 10))}
                    {doc.deletedBy && ` by ${doc.deletedBy.name}`}
                  </p>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => void restoreOne(doc)}
                  disabled={restoring !== null}
                  aria-label={`Restore ${doc.name}`}
                >
                  {restoring === doc.id ? (
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <ArchiveRestore className="h-4 w-4" aria-hidden="true" />
                  )}
                  Restore
                </Button>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}
