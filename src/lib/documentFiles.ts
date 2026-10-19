/**
 * Rules for which files can be attached to a case, checked in the browser for
 * quick feedback before anything is uploaded. The file picker and
 * drag-and-drop both go through checkFiles, so they accept and reject the
 * same files. (The picker's `accept` attribute is only a hint; a user can
 * switch the dialog to "All files".)
 *
 * The server repeats these checks and has the final say: it also verifies each
 * file's actual content against its extension and enforces the size limit.
 */

export const ACCEPTED_EXTENSIONS = [
  '.pdf',
  '.doc',
  '.docx',
  '.txt',
  '.png',
  '.jpg',
  '.jpeg',
  '.gif',
  '.webp',
] as const;

/** Value for the file input's `accept` attribute. */
export const ACCEPT_ATTRIBUTE = ACCEPTED_EXTENSIONS.join(',');

export const ACCEPTED_TYPES_LABEL = 'PDF, Word, text or image (PNG, JPG, GIF, WebP)';

export type RejectionReason = 'unsupported-type' | 'empty' | 'duplicate';

export interface FileRejection {
  name: string;
  reason: RejectionReason;
}

export interface FileCheckResult {
  accepted: File[];
  rejected: FileRejection[];
}

export const REJECTION_MESSAGES: Record<RejectionReason, string> = {
  'unsupported-type': `is not a supported file type. Use ${ACCEPTED_TYPES_LABEL}.`,
  empty: 'is empty.',
  duplicate: 'is already attached to this case.',
};

function extensionOf(fileName: string): string {
  const dot = fileName.lastIndexOf('.');
  return dot === -1 ? '' : fileName.slice(dot).toLowerCase();
}

export function isSupportedFileName(fileName: string): boolean {
  return (ACCEPTED_EXTENSIONS as readonly string[]).includes(extensionOf(fileName));
}

/**
 * Splits a selection into files to attach and files to reject.
 * A file is a duplicate if a document with the same name (ignoring case) is
 * already on the case, or if it appears twice in the same selection.
 */
export function checkFiles(
  files: readonly File[],
  existingNames: readonly string[],
): FileCheckResult {
  const taken = new Set(existingNames.map((name) => name.toLowerCase()));
  const accepted: File[] = [];
  const rejected: FileRejection[] = [];

  for (const file of files) {
    const key = file.name.toLowerCase();
    if (!isSupportedFileName(file.name)) {
      rejected.push({ name: file.name, reason: 'unsupported-type' });
    } else if (file.size === 0) {
      rejected.push({ name: file.name, reason: 'empty' });
    } else if (taken.has(key)) {
      rejected.push({ name: file.name, reason: 'duplicate' });
    } else {
      taken.add(key);
      accepted.push(file);
    }
  }

  return { accepted, rejected };
}
