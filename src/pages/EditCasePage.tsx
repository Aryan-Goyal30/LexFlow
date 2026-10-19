import { useId, useState, type FormEvent, type ReactNode } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { AlertCircle, ArrowLeft, Check, Loader2 } from 'lucide-react';
import { useAdvocates, useCase, useClientOptions, useUpdateCase } from '../hooks/useCases';
import { ApiError, errorMessage } from '../services/api/client';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { Button, ButtonLink } from '../components/ui/Button';
import { Field } from '../components/ui/Field';
import { PageHeader } from '../components/ui/PageHeader';
import { ErrorState, LoadingState } from '../components/ui/QueryState';
import { errorId, fieldProps } from '../lib/fields';
import { PRACTICE_AREAS, PRIORITIES, STATUSES } from '../lib/caseOptions';
import { casePath } from '../lib/paths';
import type {
  Advocate,
  Case,
  CaseChanges,
  CasePriority,
  CaseStatus,
  ClientOption,
  PracticeArea,
} from '../types';

/** The fields this page edits, in the order they appear (to focus the first error). */
const FIELDS = [
  'title',
  'clientId',
  'practiceArea',
  'description',
  'leadAdvocateId',
  'opposingParty',
  'courtName',
  'status',
  'priority',
] as const;
type EditField = (typeof FIELDS)[number];

type EditForm = Record<EditField, string>;
type EditErrors = Partial<Record<EditField, string>>;

const isEditField = (name: string): name is EditField =>
  (FIELDS as readonly string[]).includes(name);

function formFrom(c: Case): EditForm {
  return {
    title: c.title,
    clientId: c.clientId,
    practiceArea: c.practiceArea,
    description: c.description,
    leadAdvocateId: c.leadAdvocateId,
    opposingParty: c.opposingParty ?? '',
    courtName: c.courtName ?? '',
    status: c.status,
    priority: c.priority,
  };
}

/**
 * Only what changed, so the request never touches a field the user did not
 * edit (or may not edit). Blank optional text clears the value.
 */
function caseChanges(c: Case, form: EditForm, editable: readonly string[]): CaseChanges {
  const before = formFrom(c);
  const changes: Record<string, string | null> = {};
  for (const field of FIELDS) {
    if (!editable.includes(field)) continue;
    const value = form[field].trim();
    if (value === before[field].trim()) continue;
    const optional = field === 'courtName' || field === 'opposingParty';
    changes[field] = optional && value === '' ? null : value;
  }
  return changes as CaseChanges;
}

function checkForm(form: EditForm, editable: readonly string[]): EditErrors {
  const errors: EditErrors = {};
  if (editable.includes('title') && form.title.trim().length < 4) {
    errors.title = 'Enter a descriptive case title (at least 4 characters).';
  }
  if (editable.includes('description') && form.description.trim().length < 10) {
    errors.description = 'Provide a short summary (at least 10 characters).';
  }
  return errors;
}

export function EditCasePage() {
  const { caseId = '' } = useParams<{ caseId: string }>();
  const legalCase = useCase(caseId);
  const editable = legalCase.data?.permissions.editableFields ?? [];
  // Only load the lists this user can actually choose from.
  const clients = useClientOptions({ enabled: editable.includes('clientId') });
  const advocates = useAdvocates({ enabled: editable.includes('leadAdvocateId') });

  let body: ReactNode;
  const notFound = legalCase.error instanceof ApiError && legalCase.error.isNotFound;
  if (legalCase.isPending) {
    body = (
      <Card>
        <LoadingState label="Loading the case…" />
      </Card>
    );
  } else if (!legalCase.data || notFound) {
    body = (
      <Card>
        <ErrorState
          title={notFound ? 'Case not found' : "Couldn't load the case"}
          error={legalCase.error}
          onRetry={notFound ? undefined : () => legalCase.refetch()}
        />
      </Card>
    );
  } else if (editable.length === 0) {
    const c = legalCase.data;
    body = (
      <Card className="px-6 py-10 text-center">
        <p role="status" className="text-sm text-brand-700">
          {c.archivedAt
            ? 'This case is archived, so it cannot be changed. An administrator can restore it.'
            : 'You can view this case but not change its details.'}
        </p>
        <ButtonLink to={casePath(c.id)} variant="secondary" className="mt-4">
          Back to the case
        </ButtonLink>
      </Card>
    );
  } else if (
    (editable.includes('clientId') && clients.isPending) ||
    (editable.includes('leadAdvocateId') && advocates.isPending)
  ) {
    body = (
      <Card>
        <LoadingState label="Loading the form…" />
      </Card>
    );
  } else if (clients.isError || advocates.isError) {
    body = (
      <Card>
        <ErrorState
          title="Couldn't load the form"
          error={clients.error ?? advocates.error}
          onRetry={() => {
            void clients.refetch();
            void advocates.refetch();
          }}
        />
      </Card>
    );
  } else {
    body = (
      <EditCaseForm
        key={legalCase.data.id}
        legalCase={legalCase.data}
        clients={clients.data ?? []}
        advocates={advocates.data ?? []}
      />
    );
  }

  return (
    <>
      <Link
        to={casePath(caseId)}
        className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-brand-600 hover:text-brand-800"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Back to the case
      </Link>
      <PageHeader
        title="Edit Case"
        description={
          legalCase.data
            ? `${legalCase.data.caseNumber} · ${legalCase.data.title}`
            : 'Change the details of a case.'
        }
      />
      {body}
    </>
  );
}

function EditCaseForm({
  legalCase: c,
  clients,
  advocates,
}: {
  legalCase: Case;
  clients: ClientOption[];
  advocates: Advocate[];
}) {
  const navigate = useNavigate();
  const update = useUpdateCase(c.id);
  const uid = useId();
  const editable = c.permissions.editableFields;
  const may = (field: EditField) => editable.includes(field);

  const [form, setForm] = useState<EditForm>(() => formFrom(c));
  const [errors, setErrors] = useState<EditErrors>({});
  const [saveError, setSaveError] = useState<string | null>(null);
  const [nothingChanged, setNothingChanged] = useState(false);

  const props = (field: EditField) => fieldProps(uid, field, errors[field]);
  const set = (field: EditField, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: undefined }));
    setNothingChanged(false);
  };

  const showErrors = (found: EditErrors): boolean => {
    setErrors(found);
    const first = FIELDS.find((field) => found[field]);
    if (first) document.getElementById(`${uid}-${first}`)?.focus();
    return first !== undefined;
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (update.isPending) return;
    setSaveError(null);
    if (showErrors(checkForm(form, editable))) return;
    const changes = caseChanges(c, form, editable);
    if (Object.keys(changes).length === 0) {
      setNothingChanged(true);
      return;
    }
    update.mutate(changes, {
      onSuccess: (updated) => navigate(casePath(updated.id)),
      onError: (error) => {
        if (error instanceof ApiError && Object.keys(error.fieldErrors).length > 0) {
          const fromServer: EditErrors = {};
          const other: string[] = [];
          for (const [field, message] of Object.entries(error.fieldErrors)) {
            if (isEditField(field)) fromServer[field] = message;
            else other.push(message);
          }
          showErrors(fromServer);
          if (other.length > 0) setSaveError(other.join(' '));
        } else {
          setSaveError(`The changes were not saved. ${errorMessage(error)}`);
        }
      },
    });
  };

  const errorCount = Object.values(errors).filter(Boolean).length;
  const saving = update.isPending;
  const readOnlyNote =
    c.permissions.relation === 'paralegal'
      ? 'As a paralegal on this case you can update the court and the opposing party.'
      : null;

  return (
    <>
      {(errorCount > 0 || saveError) && (
        <div
          role="alert"
          className="mb-4 flex items-start gap-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-inset ring-red-600/20"
        >
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <div>
            {errorCount > 0 && (
              <p>
                {errorCount === 1
                  ? 'One field needs attention before the changes can be saved.'
                  : `${errorCount} fields need attention before the changes can be saved.`}
              </p>
            )}
            {saveError && <p>{saveError}</p>}
          </div>
        </div>
      )}
      {readOnlyNote && (
        <p className="mb-4 text-sm text-brand-600" role="note">
          {readOnlyNote}
        </p>
      )}

      <form onSubmit={handleSubmit} noValidate aria-label="Edit case" aria-busy={saving}>
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            {(may('title') || may('clientId') || may('practiceArea') || may('description')) && (
              <Card>
                <CardHeader title="Case Information" />
                <CardBody className="space-y-4">
                  {may('title') && (
                    <Field
                      label="Case Title"
                      htmlFor={`${uid}-title`}
                      error={errors.title}
                      errorId={errorId(uid, 'title')}
                      required
                    >
                      <input
                        {...props('title')}
                        className="input-field"
                        value={form.title}
                        onChange={(e) => set('title', e.target.value)}
                        required
                      />
                    </Field>
                  )}
                  <div className="grid gap-4 sm:grid-cols-2">
                    {may('clientId') && (
                      <Field
                        label="Client"
                        htmlFor={`${uid}-clientId`}
                        error={errors.clientId}
                        errorId={errorId(uid, 'clientId')}
                      >
                        <select
                          {...props('clientId')}
                          className="input-field"
                          value={form.clientId}
                          onChange={(e) => set('clientId', e.target.value)}
                        >
                          {clients.map((client) => (
                            <option key={client.id} value={client.id}>
                              {client.name}
                              {client.isSample ? ' (sample)' : ''}
                            </option>
                          ))}
                        </select>
                      </Field>
                    )}
                    {may('practiceArea') && (
                      <Field
                        label="Practice Area"
                        htmlFor={`${uid}-practiceArea`}
                        error={errors.practiceArea}
                        errorId={errorId(uid, 'practiceArea')}
                      >
                        <select
                          {...props('practiceArea')}
                          className="input-field"
                          value={form.practiceArea}
                          onChange={(e) => set('practiceArea', e.target.value as PracticeArea)}
                        >
                          {PRACTICE_AREAS.map((area) => (
                            <option key={area}>{area}</option>
                          ))}
                        </select>
                      </Field>
                    )}
                  </div>
                  {may('description') && (
                    <Field
                      label="Summary"
                      htmlFor={`${uid}-description`}
                      error={errors.description}
                      errorId={errorId(uid, 'description')}
                      required
                    >
                      <textarea
                        {...props('description')}
                        className="input-field min-h-[110px] resize-y"
                        value={form.description}
                        onChange={(e) => set('description', e.target.value)}
                        required
                      />
                    </Field>
                  )}
                </CardBody>
              </Card>
            )}

            <Card>
              <CardHeader title="Parties & Court" />
              <CardBody className="grid gap-4 sm:grid-cols-2">
                {may('leadAdvocateId') && (
                  <Field
                    label="Lead Advocate"
                    htmlFor={`${uid}-leadAdvocateId`}
                    error={errors.leadAdvocateId}
                    errorId={errorId(uid, 'leadAdvocateId')}
                    hint="The new lead leaves the case team, if they were on it."
                  >
                    <select
                      {...props('leadAdvocateId')}
                      className="input-field"
                      value={form.leadAdvocateId}
                      onChange={(e) => set('leadAdvocateId', e.target.value)}
                    >
                      {/* The current lead stays listed even if no longer active. */}
                      {!advocates.some((a) => a.id === c.leadAdvocateId) && (
                        <option value={c.leadAdvocateId}>{c.leadAttorney}</option>
                      )}
                      {advocates.map((advocate) => (
                        <option key={advocate.id} value={advocate.id}>
                          {advocate.name}
                        </option>
                      ))}
                    </select>
                  </Field>
                )}
                {may('opposingParty') && (
                  <Field
                    label="Opposing Party"
                    htmlFor={`${uid}-opposingParty`}
                    error={errors.opposingParty}
                    errorId={errorId(uid, 'opposingParty')}
                  >
                    <input
                      {...props('opposingParty')}
                      className="input-field"
                      value={form.opposingParty}
                      onChange={(e) => set('opposingParty', e.target.value)}
                    />
                  </Field>
                )}
                {may('courtName') && (
                  <Field
                    label="Court / Forum"
                    htmlFor={`${uid}-courtName`}
                    error={errors.courtName}
                    errorId={errorId(uid, 'courtName')}
                  >
                    <input
                      {...props('courtName')}
                      className="input-field"
                      value={form.courtName}
                      onChange={(e) => set('courtName', e.target.value)}
                    />
                  </Field>
                )}
              </CardBody>
            </Card>
          </div>

          <div className="space-y-6">
            {(may('status') || may('priority')) && (
              <Card>
                <CardHeader title="Classification" />
                <CardBody className="space-y-4">
                  {may('status') && (
                    <Field
                      label="Status"
                      htmlFor={`${uid}-status`}
                      error={errors.status}
                      errorId={errorId(uid, 'status')}
                    >
                      <select
                        {...props('status')}
                        className="input-field"
                        value={form.status}
                        onChange={(e) => set('status', e.target.value as CaseStatus)}
                      >
                        {STATUSES.map((s) => (
                          <option key={s}>{s}</option>
                        ))}
                      </select>
                    </Field>
                  )}
                  {may('priority') && (
                    <Field
                      label="Priority"
                      htmlFor={`${uid}-priority`}
                      error={errors.priority}
                      errorId={errorId(uid, 'priority')}
                    >
                      <select
                        {...props('priority')}
                        className="input-field"
                        value={form.priority}
                        onChange={(e) => set('priority', e.target.value as CasePriority)}
                      >
                        {PRIORITIES.map((p) => (
                          <option key={p}>{p}</option>
                        ))}
                      </select>
                    </Field>
                  )}
                </CardBody>
              </Card>
            )}

            <div className="flex flex-col gap-2">
              {nothingChanged && (
                <p role="status" className="text-sm text-brand-600">
                  Nothing has changed yet.
                </p>
              )}
              <Button type="submit" className="w-full" disabled={saving}>
                {saving ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Check className="h-4 w-4" aria-hidden="true" />
                )}
                {saving ? 'Saving…' : 'Save Changes'}
              </Button>
              <ButtonLink to={casePath(c.id)} variant="secondary" className="w-full">
                Cancel
              </ButtonLink>
            </div>
          </div>
        </div>
      </form>
    </>
  );
}
