/** Shared wiring for form controls rendered with `components/ui/Field`. */

/** Ids and ARIA wiring for one control of a form, given a `useId()` prefix. */
export function fieldProps(prefix: string, name: string, error: string | undefined) {
  return {
    id: `${prefix}-${name}`,
    'aria-invalid': error ? true : undefined,
    'aria-describedby': error ? `${prefix}-${name}-error` : undefined,
  };
}

export const errorId = (prefix: string, name: string) => `${prefix}-${name}-error`;
