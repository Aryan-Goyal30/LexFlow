import { useId, useState, type FormEvent, type ReactNode } from 'react';
import { AlertCircle, Check, Loader2 } from 'lucide-react';
import type { ClientField, ClientFormValues } from '../../lib/clientForm';
import { ApiError, errorMessage } from '../../services/api/client';
import { Button } from '../ui/Button';
import { Field } from '../ui/Field';
import { errorId, fieldProps } from '../../lib/fields';

type ClientErrors = Partial<Record<ClientField, string>>;

const FIELDS: ClientField[] = ['name', 'company', 'email', 'phone'];
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const PHONE = /^\+?[0-9 ()-]{7,20}$/;

/** The same rules as the server, for quick feedback; the server checks again. */
function checkClient(values: ClientFormValues): ClientErrors {
  const errors: ClientErrors = {};
  if (values.name.trim().length < 2) {
    errors.name = "Enter the client's name (at least 2 characters).";
  }
  if (!EMAIL.test(values.email.trim())) {
    errors.email = 'Enter an e-mail address such as name@example.com.';
  }
  if (!PHONE.test(values.phone.trim())) {
    errors.phone = 'Enter a phone number: digits, spaces, +, - or brackets (7 to 20).';
  }
  if (values.company.trim().length > 200) errors.company = 'Keep this under 201 characters.';
  return errors;
}

/**
 * Name, company and contact details of a client, checked before `onSubmit`.
 * `onSubmit` returns a promise; a rejected one shows the server's reasons.
 */
export function ClientForm({
  initial,
  label,
  submitLabel,
  busyLabel,
  failurePrefix,
  onSubmit,
  cancel,
}: {
  initial: ClientFormValues;
  label: string;
  submitLabel: string;
  busyLabel: string;
  failurePrefix: string;
  onSubmit: (values: ClientFormValues) => Promise<unknown>;
  cancel: ReactNode;
}) {
  const uid = useId();
  const [values, setValues] = useState(initial);
  const [errors, setErrors] = useState<ClientErrors>({});
  const [failure, setFailure] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const props = (field: ClientField) => fieldProps(uid, field, errors[field]);
  const set = (field: ClientField, value: string) => {
    setValues((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: undefined }));
  };
  const show = (found: ClientErrors) => {
    setErrors(found);
    const first = FIELDS.find((f) => found[f]);
    if (first) document.getElementById(`${uid}-${first}`)?.focus();
    return first !== undefined;
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setFailure(null);
    if (show(checkClient(values))) return;
    setBusy(true);
    try {
      await onSubmit(values);
    } catch (error) {
      if (error instanceof ApiError && Object.keys(error.fieldErrors).length > 0) {
        const found: ClientErrors = {};
        for (const [field, message] of Object.entries(error.fieldErrors)) {
          if ((FIELDS as string[]).includes(field)) found[field as ClientField] = message;
        }
        show(found);
      } else {
        setFailure(`${failurePrefix} ${errorMessage(error)}`);
      }
    } finally {
      setBusy(false);
    }
  };

  const errorCount = Object.values(errors).filter(Boolean).length;
  return (
    <form onSubmit={(e) => void submit(e)} noValidate aria-label={label} aria-busy={busy}>
      {(errorCount > 0 || failure) && (
        <div
          role="alert"
          className="mb-4 flex items-start gap-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-inset ring-red-600/20"
        >
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <p>
            {failure ??
              (errorCount === 1
                ? 'One field needs attention.'
                : `${errorCount} fields need attention.`)}
          </p>
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          label="Name"
          htmlFor={`${uid}-name`}
          error={errors.name}
          errorId={errorId(uid, 'name')}
          required
        >
          <input
            {...props('name')}
            className="input-field"
            value={values.name}
            onChange={(e) => set('name', e.target.value)}
          />
        </Field>
        <Field
          label="Company"
          htmlFor={`${uid}-company`}
          error={errors.company}
          errorId={errorId(uid, 'company')}
        >
          <input
            {...props('company')}
            className="input-field"
            value={values.company}
            onChange={(e) => set('company', e.target.value)}
          />
        </Field>
        <Field
          label="E-mail"
          htmlFor={`${uid}-email`}
          error={errors.email}
          errorId={errorId(uid, 'email')}
          required
        >
          <input
            {...props('email')}
            type="email"
            className="input-field"
            value={values.email}
            onChange={(e) => set('email', e.target.value)}
          />
        </Field>
        <Field
          label="Phone"
          htmlFor={`${uid}-phone`}
          error={errors.phone}
          errorId={errorId(uid, 'phone')}
          required
        >
          <input
            {...props('phone')}
            type="tel"
            className="input-field"
            value={values.phone}
            onChange={(e) => set('phone', e.target.value)}
          />
        </Field>
      </div>
      <div className="mt-4 flex gap-2">
        <Button type="submit" disabled={busy}>
          {busy ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <Check className="h-4 w-4" aria-hidden="true" />
          )}
          {busy ? busyLabel : submitLabel}
        </Button>
        {cancel}
      </div>
    </form>
  );
}
