import { useEffect, useId, useRef, useState, type FormEvent } from 'react';
import { CalendarPlus, Clock, Loader2, Pencil, XCircle } from 'lucide-react';
import type { Case, Hearing, HearingChanges, HearingInput } from '../../types';
import { useCancelHearing, useScheduleHearing, useUpdateHearing } from '../../hooks/useCases';
import { ApiError, errorMessage } from '../../services/api/client';
import { Card, CardBody, CardHeader } from '../ui/Card';
import { Button } from '../ui/Button';
import { Field } from '../ui/Field';
import { errorId, fieldProps } from '../../lib/fields';
import { formatDate, todayIsoDate } from '../../lib/format';

type HearingField = 'date' | 'time' | 'court' | 'purpose';
type HearingForm = Record<HearingField, string>;
type HearingErrors = Partial<Record<HearingField, string>>;

const FIELDS: HearingField[] = ['date', 'time', 'court', 'purpose'];
const TIME = /^([01]\d|2[0-3]):[0-5]\d$/;

/** The same rules as the server, for quick feedback; the server checks again. */
function checkHearing(form: HearingForm, today: string): HearingErrors {
  const errors: HearingErrors = {};
  if (!form.date) errors.date = 'Enter the hearing date.';
  else if (form.date < today) errors.date = 'The hearing date cannot be in the past.';
  if (form.time && !TIME.test(form.time)) {
    errors.time = 'Enter the time as HH:MM (24-hour), or leave it blank.';
  }
  if (!form.court.trim()) errors.court = 'Enter the court or forum.';
  if (!form.purpose.trim()) errors.purpose = 'Enter the purpose of the hearing.';
  return errors;
}

/**
 * The case's hearings. Staff on the case schedule, change and cancel them;
 * cancelled hearings stay listed, with the reason, but are never the next
 * hearing.
 */
export function HearingsCard({ legalCase: c }: { legalCase: Case }) {
  const manage = c.permissions.canManageHearings;
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const startAdding = () => {
    setEditing(null);
    setCancelling(null);
    setNotice(null);
    setAdding(true);
  };

  return (
    <Card>
      <CardHeader
        title="Hearings"
        action={
          manage && !adding ? (
            <Button variant="ghost" size="sm" onClick={startAdding}>
              <CalendarPlus className="h-4 w-4" aria-hidden="true" />
              Schedule hearing
            </Button>
          ) : undefined
        }
      />
      <CardBody className="p-0">
        <div aria-live="polite">
          {notice && (
            <p className="mx-5 mt-3 rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-800 ring-1 ring-inset ring-emerald-600/20">
              {notice}
            </p>
          )}
        </div>
        {adding && (
          <div className="border-b border-brand-100 px-5 py-4">
            <ScheduleForm
              legalCase={c}
              onDone={(message) => {
                setAdding(false);
                if (message) setNotice(message);
              }}
            />
          </div>
        )}
        {c.hearings.length === 0 ? (
          <p className="px-5 py-6 text-sm text-brand-500">No hearings scheduled.</p>
        ) : (
          <ul className="divide-y divide-brand-100" aria-label="Hearings">
            {c.hearings.map((h) => {
              const cancelled = h.status === 'Cancelled';
              return (
                <li key={h.id} className="px-5 py-3">
                  {editing === h.id ? (
                    <EditForm
                      legalCase={c}
                      hearing={h}
                      onDone={(message) => {
                        setEditing(null);
                        if (message) setNotice(message);
                      }}
                    />
                  ) : (
                    <>
                      <div className="flex items-start justify-between gap-2">
                        <div className={cancelled ? 'text-brand-400' : undefined}>
                          <p
                            className={`text-sm font-medium ${
                              cancelled ? 'text-brand-500 line-through' : 'text-brand-900'
                            }`}
                          >
                            {h.purpose}
                          </p>
                          <p className="mt-1 flex items-center gap-1.5 text-xs text-brand-500">
                            <Clock className="h-3.5 w-3.5" aria-hidden="true" />
                            {formatDate(h.date)} · {h.time ?? 'time to be confirmed'} · {h.court}
                          </p>
                          {cancelled && (
                            <p className="mt-1 text-xs font-medium text-red-700">
                              Cancelled
                              {h.cancellationReason && (
                                <span className="font-normal text-brand-600">
                                  {' '}
                                  · {h.cancellationReason}
                                </span>
                              )}
                            </p>
                          )}
                        </div>
                        {manage && !cancelled && cancelling !== h.id && (
                          <div className="flex shrink-0 gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              aria-label={`Change hearing: ${h.purpose}`}
                              onClick={() => {
                                setAdding(false);
                                setCancelling(null);
                                setNotice(null);
                                setEditing(h.id);
                              }}
                            >
                              <Pencil className="h-4 w-4" aria-hidden="true" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              aria-label={`Cancel hearing: ${h.purpose}`}
                              onClick={() => {
                                setEditing(null);
                                setNotice(null);
                                setCancelling(h.id);
                              }}
                            >
                              <XCircle className="h-4 w-4" aria-hidden="true" />
                            </Button>
                          </div>
                        )}
                      </div>
                      {cancelling === h.id && (
                        <CancelPrompt
                          legalCase={c}
                          hearing={h}
                          onDone={(message) => {
                            setCancelling(null);
                            if (message) setNotice(message);
                          }}
                        />
                      )}
                    </>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}

function useHearingForm(initial: HearingForm) {
  const uid = useId();
  const [form, setForm] = useState(initial);
  const [errors, setErrors] = useState<HearingErrors>({});
  const [failure, setFailure] = useState<string | null>(null);

  const show = (found: HearingErrors) => {
    setErrors(found);
    const first = FIELDS.find((f) => found[f]);
    if (first) document.getElementById(`${uid}-${first}`)?.focus();
    return first !== undefined;
  };

  const fail = (error: unknown, what: string) => {
    if (error instanceof ApiError && Object.keys(error.fieldErrors).length > 0) {
      const found: HearingErrors = {};
      for (const [field, message] of Object.entries(error.fieldErrors)) {
        if ((FIELDS as string[]).includes(field)) found[field as HearingField] = message;
      }
      show(found);
    } else {
      setFailure(`${what} ${errorMessage(error)}`);
    }
  };

  const set = (field: HearingField, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: undefined }));
  };

  return { uid, form, errors, failure, setFailure, show, fail, set };
}

function HearingFields({ state }: { state: ReturnType<typeof useHearingForm> }) {
  const { uid, form, errors, set } = state;
  const props = (field: HearingField) => fieldProps(uid, field, errors[field]);
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Field
        label="Date"
        htmlFor={`${uid}-date`}
        error={errors.date}
        errorId={errorId(uid, 'date')}
        required
      >
        <input
          {...props('date')}
          type="date"
          min={todayIsoDate()}
          className="input-field"
          value={form.date}
          onChange={(e) => set('date', e.target.value)}
        />
      </Field>
      <Field
        label="Time"
        htmlFor={`${uid}-time`}
        error={errors.time}
        errorId={errorId(uid, 'time')}
        hint="Leave blank until the court lists it."
      >
        <input
          {...props('time')}
          type="time"
          className="input-field"
          value={form.time}
          onChange={(e) => set('time', e.target.value)}
        />
      </Field>
      <Field
        label="Court / Forum"
        htmlFor={`${uid}-court`}
        error={errors.court}
        errorId={errorId(uid, 'court')}
        required
      >
        <input
          {...props('court')}
          className="input-field"
          value={form.court}
          onChange={(e) => set('court', e.target.value)}
        />
      </Field>
      <Field
        label="Purpose"
        htmlFor={`${uid}-purpose`}
        error={errors.purpose}
        errorId={errorId(uid, 'purpose')}
        required
      >
        <input
          {...props('purpose')}
          className="input-field"
          value={form.purpose}
          onChange={(e) => set('purpose', e.target.value)}
        />
      </Field>
    </div>
  );
}

function FormButtons({
  busy,
  label,
  busyLabel,
  onCancel,
  failure,
}: {
  busy: boolean;
  label: string;
  busyLabel: string;
  onCancel: () => void;
  failure: string | null;
}) {
  return (
    <>
      {failure && (
        <p role="alert" className="mt-2 text-sm text-red-600">
          {failure}
        </p>
      )}
      <div className="mt-3 flex gap-2">
        <Button type="submit" size="sm" disabled={busy}>
          {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
          {busy ? busyLabel : label}
        </Button>
        <Button variant="ghost" size="sm" onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
      </div>
    </>
  );
}

function ScheduleForm({
  legalCase: c,
  onDone,
}: {
  legalCase: Case;
  onDone: (message: string | null) => void;
}) {
  const schedule = useScheduleHearing(c.id);
  const state = useHearingForm({ date: '', time: '', court: c.courtName ?? '', purpose: '' });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (schedule.isPending) return;
    state.setFailure(null);
    if (state.show(checkHearing(state.form, todayIsoDate()))) return;
    const input: HearingInput = {
      date: state.form.date,
      time: state.form.time || null,
      court: state.form.court,
      purpose: state.form.purpose,
    };
    schedule.mutate(input, {
      onSuccess: () => onDone(`Hearing scheduled for ${formatDate(input.date)}.`),
      onError: (error) => state.fail(error, 'The hearing was not scheduled.'),
    });
  };

  return (
    <form onSubmit={submit} noValidate aria-label="Schedule a hearing">
      <HearingFields state={state} />
      <FormButtons
        busy={schedule.isPending}
        label="Schedule"
        busyLabel="Scheduling…"
        onCancel={() => onDone(null)}
        failure={state.failure}
      />
    </form>
  );
}

function EditForm({
  legalCase: c,
  hearing: h,
  onDone,
}: {
  legalCase: Case;
  hearing: Hearing;
  onDone: (message: string | null) => void;
}) {
  const update = useUpdateHearing(c.id);
  const state = useHearingForm({
    date: h.date,
    time: h.time ?? '',
    court: h.court,
    purpose: h.purpose,
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (update.isPending) return;
    state.setFailure(null);
    // An unchanged past date (a hearing being corrected) is not re-checked.
    const today = state.form.date === h.date ? '' : todayIsoDate();
    if (state.show(checkHearing(state.form, today))) return;
    const changes: HearingChanges = {};
    if (state.form.date !== h.date) changes.date = state.form.date;
    if (state.form.time !== (h.time ?? '')) changes.time = state.form.time || null;
    if (state.form.court.trim() !== h.court) changes.court = state.form.court;
    if (state.form.purpose.trim() !== h.purpose) changes.purpose = state.form.purpose;
    if (Object.keys(changes).length === 0) {
      onDone(null);
      return;
    }
    update.mutate(
      { id: h.id, changes },
      {
        onSuccess: () => onDone('Hearing updated.'),
        onError: (error) => state.fail(error, 'The hearing was not changed.'),
      },
    );
  };

  return (
    <form onSubmit={submit} noValidate aria-label={`Change hearing: ${h.purpose}`}>
      <HearingFields state={state} />
      <FormButtons
        busy={update.isPending}
        label="Save"
        busyLabel="Saving…"
        onCancel={() => onDone(null)}
        failure={state.failure}
      />
    </form>
  );
}

function CancelPrompt({
  legalCase: c,
  hearing: h,
  onDone,
}: {
  legalCase: Case;
  hearing: Hearing;
  onDone: (message: string | null) => void;
}) {
  const cancel = useCancelHearing(c.id);
  const [reason, setReason] = useState('');
  const reasonId = useId();
  const promptId = useId();
  const reasonRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => reasonRef.current?.focus(), []);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (cancel.isPending) return;
    cancel.mutate(
      { id: h.id, reason: reason.trim() },
      { onSuccess: () => onDone(`Hearing on ${formatDate(h.date)} cancelled.`) },
    );
  };

  return (
    <form
      onSubmit={submit}
      aria-labelledby={promptId}
      className="mt-2 rounded-md bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-inset ring-amber-600/30"
    >
      <p id={promptId}>
        Cancel this hearing? It stays on the case, marked cancelled, and no longer counts as the
        next hearing.
      </p>
      <label htmlFor={reasonId} className="label-text mt-2">
        Reason (optional)
      </label>
      <textarea
        ref={reasonRef}
        id={reasonId}
        className="input-field min-h-[60px]"
        maxLength={500}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
      />
      {cancel.isError && (
        <p role="alert" className="mt-2 text-red-700">
          The hearing was not cancelled. {errorMessage(cancel.error)}
        </p>
      )}
      <div className="mt-2 flex gap-2">
        <Button type="submit" variant="danger" size="sm" disabled={cancel.isPending}>
          {cancel.isPending && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
          Cancel hearing
        </Button>
        <Button variant="ghost" size="sm" onClick={() => onDone(null)} disabled={cancel.isPending}>
          Keep it
        </Button>
      </div>
    </form>
  );
}
