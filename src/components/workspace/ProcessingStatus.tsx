import { AlertCircle, CheckCircle2, Clock, Loader2, MinusCircle } from 'lucide-react';
import type { DocumentProcessing } from '../../types';

function count(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}

/**
 * The text-extraction status of a stored document, as the server reports it.
 * Records without a file (sample records) have no status and show nothing.
 */
export function ProcessingStatus({ processing }: { processing: DocumentProcessing | null }) {
  if (!processing) return null;
  const { status } = processing;
  if (status === 'queued') {
    return (
      <p className="mt-0.5 flex items-center gap-1 text-xs text-brand-500">
        <Clock className="h-3.5 w-3.5" aria-hidden="true" />
        Waiting for text extraction
      </p>
    );
  }
  if (status === 'processing') {
    return (
      <p className="mt-0.5 flex items-center gap-1 text-xs text-brand-500">
        <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
        Extracting text…
      </p>
    );
  }
  if (status === 'ready') {
    const size =
      processing.pageCount !== null
        ? count(processing.pageCount, 'page', 'pages')
        : count(processing.sectionCount ?? 0, 'part', 'parts');
    return (
      <p className="mt-0.5 flex items-center gap-1 text-xs text-emerald-700">
        <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
        Text extracted · {size}
      </p>
    );
  }
  if (status === 'failed') {
    return (
      <p className="mt-0.5 flex items-start gap-1 text-xs text-red-700">
        <AlertCircle className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        <span>Text extraction failed: {processing.reason}</span>
      </p>
    );
  }
  return (
    <p className="mt-0.5 flex items-start gap-1 text-xs text-brand-500">
      <MinusCircle className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <span>{processing.reason}</span>
    </p>
  );
}
