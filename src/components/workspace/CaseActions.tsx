import { useEffect, useId, useRef, useState } from 'react';
import { Archive, ArchiveRestore, Loader2, Pencil } from 'lucide-react';
import type { Case } from '../../types';
import { useSetArchived } from '../../hooks/useCases';
import { errorMessage } from '../../services/api/client';
import { Button, ButtonLink } from '../ui/Button';
import { editCasePath } from '../../lib/paths';
import { formatDate } from '../../lib/format';

/** Edit and Archive / Restore, shown only to those the server would allow. */
export function CaseActions({ legalCase: c }: { legalCase: Case }) {
  const { editableFields, canArchive } = c.permissions;
  if (editableFields.length === 0 && !canArchive) return null;
  return (
    <div className="flex flex-wrap items-start gap-2">
      {editableFields.length > 0 && (
        <ButtonLink to={editCasePath(c.id)} variant="secondary" size="sm">
          <Pencil className="h-4 w-4" aria-hidden="true" />
          Edit case
        </ButtonLink>
      )}
      {canArchive && <ArchiveControl legalCase={c} />}
    </div>
  );
}

/** Archiving asks for confirmation first; restoring does not (nothing is lost either way). */
function ArchiveControl({ legalCase: c }: { legalCase: Case }) {
  const setArchived = useSetArchived(c.id);
  const [confirming, setConfirming] = useState(false);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const promptId = useId();
  const archived = c.archivedAt !== null;
  const busy = setArchived.isPending;

  useEffect(() => {
    if (confirming) confirmRef.current?.focus();
  }, [confirming]);

  const run = (archive: boolean) =>
    setArchived.mutate(archive, { onSettled: () => setConfirming(false) });

  if (archived) {
    return (
      <div>
        <Button variant="secondary" size="sm" onClick={() => run(false)} disabled={busy}>
          {busy ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <ArchiveRestore className="h-4 w-4" aria-hidden="true" />
          )}
          Restore case
        </Button>
        {setArchived.isError && (
          <p role="alert" className="mt-1 text-xs text-red-600">
            The case was not restored. {errorMessage(setArchived.error)}
          </p>
        )}
      </div>
    );
  }

  if (!confirming) {
    return (
      <div>
        <Button
          ref={triggerRef}
          variant="secondary"
          size="sm"
          onClick={() => {
            setArchived.reset();
            setConfirming(true);
          }}
        >
          <Archive className="h-4 w-4" aria-hidden="true" />
          Archive case
        </Button>
        {setArchived.isError && (
          <p role="alert" className="mt-1 text-xs text-red-600">
            The case was not archived. {errorMessage(setArchived.error)}
          </p>
        )}
      </div>
    );
  }

  return (
    <div
      role="group"
      aria-labelledby={promptId}
      className="max-w-sm rounded-md bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-inset ring-amber-600/30"
    >
      <p id={promptId}>
        Archive this case? It stays in full but becomes read-only and leaves the case list until an
        administrator restores it.
      </p>
      <div className="mt-2 flex gap-2">
        <Button ref={confirmRef} size="sm" onClick={() => run(true)} disabled={busy}>
          {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
          Archive
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            setConfirming(false);
            // Return focus to where the user was.
            requestAnimationFrame(() => triggerRef.current?.focus());
          }}
          disabled={busy}
        >
          Cancel
        </Button>
      </div>
    </div>
  );
}

/** Says plainly that an archived case is read-only, and when it was archived. */
export function ArchivedNotice({ legalCase: c }: { legalCase: Case }) {
  if (!c.archivedAt) return null;
  return (
    <div
      role="status"
      className="mb-4 rounded-md bg-brand-100 px-4 py-3 text-sm text-brand-800 ring-1 ring-inset ring-brand-600/20"
    >
      <p className="font-medium">Archived on {formatDate(c.archivedAt.slice(0, 10))}</p>
      <p className="mt-0.5">
        This case is read-only: its details, team and documents cannot be changed
        {c.permissions.canArchive ? ' until you restore it.' : '. An administrator can restore it.'}
      </p>
    </div>
  );
}
