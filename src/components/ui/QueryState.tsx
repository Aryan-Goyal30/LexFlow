import { AlertCircle, Loader2, RefreshCw } from 'lucide-react';
import { errorMessage } from '../../services/api/client';
import { Button } from './Button';

/** Shown while data is loading. Announced politely to screen readers. */
export function LoadingState({ label, className = '' }: { label: string; className?: string }) {
  return (
    <div
      role="status"
      className={`flex items-center justify-center gap-2 px-6 py-12 text-sm text-brand-500 ${className}`}
    >
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      {label}
    </div>
  );
}

/**
 * Shown above data that is still on screen after a refresh failed, so one
 * failed background refresh never replaces a working page with an error.
 */
export function StaleDataNotice({
  error,
  onRetry,
  className = '',
}: {
  error: unknown;
  onRetry: () => void;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={`flex flex-wrap items-center justify-between gap-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800 ring-1 ring-inset ring-amber-600/20 ${className}`}
    >
      <span>Couldn&apos;t refresh, so this may be out of date. {errorMessage(error)}</span>
      <Button variant="secondary" size="sm" onClick={onRetry}>
        <RefreshCw className="h-4 w-4" aria-hidden="true" />
        Try again
      </Button>
    </div>
  );
}

/** Shown when loading failed, with the server's explanation and a retry. */
export function ErrorState({
  title,
  error,
  onRetry,
  className = '',
}: {
  title: string;
  error: unknown;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={`flex flex-col items-center justify-center px-6 py-12 text-center ${className}`}
    >
      <AlertCircle className="h-9 w-9 text-red-400" strokeWidth={1.5} aria-hidden="true" />
      <p className="mt-3 text-sm font-medium text-brand-800">{title}</p>
      <p className="mt-1 max-w-md text-sm text-brand-500">{errorMessage(error)}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" className="mt-4" onClick={onRetry}>
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Try again
        </Button>
      )}
    </div>
  );
}
