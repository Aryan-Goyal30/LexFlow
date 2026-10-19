import type { ReactNode } from 'react';

/**
 * A labelled form control with its error message. Pair it with
 * `aria-invalid` / `aria-describedby` on the control (see `fieldProps`).
 */
export function Field({
  label,
  htmlFor,
  error,
  errorId,
  required,
  hint,
  children,
}: {
  label: string;
  htmlFor: string;
  error?: string;
  errorId?: string;
  required?: boolean;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div>
      <label className="label-text" htmlFor={htmlFor}>
        {label}
        {required && (
          <span className="ml-0.5 text-red-500" aria-hidden="true">
            *
          </span>
        )}
      </label>
      {children}
      {hint && !error && <p className="mt-1 text-xs text-brand-400">{hint}</p>}
      {error && (
        <p id={errorId} className="mt-1 text-xs text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}
