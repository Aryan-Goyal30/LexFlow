# 0013 — Nothing is destroyed in the app: archive, cancel, soft delete, guarded purge

Status: Accepted (Phase 2)

## Context

Legal records must not vanish by a mis-click, and who removed what must stay
known. Yet files that genuinely must go (a document uploaded to the wrong
matter) need a way out.

## Decision

- **Cases are archived**, never deleted (Administrators; restorable).
- **Hearings are cancelled**, never deleted: kept with the reason, no longer
  the next or an upcoming hearing.
- **Documents are deleted softly** (`deleted_at`, `deleted_by_id`): the record
  and file stay; the document disappears from the case, lists and downloads.
  The Administrator or the lead advocate can list and restore them. A deleted
  document's name may be reused (the unique index covers live documents only);
  restoring waits until the name is free.
- **Purging is a separate, guarded command**, never automatic:
  `python -m lexflow.cli.documents purge --older-than-days N | --document ID`
  previews first and changes nothing without `--confirm N` matching the
  previewed count; it only ever touches deleted documents, never on archived
  cases, re-checks each row under a lock, and audits each purge as made from
  the command line.
- **Clients are never deleted** (cases refer to them).

## Consequences

- Storage grows until an operator purges; that is the intended trade-off.
- Downgrading migrations 0005 and 0006 refuses (changing nothing) when data
  would be misrepresented: deleted documents sharing a name with live ones, or
  cancelled hearings that would turn back into scheduled ones.
