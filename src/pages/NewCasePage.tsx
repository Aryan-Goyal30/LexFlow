import { useId, useState, type FormEvent, type ReactNode } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { AlertCircle, ArrowLeft, Check, Loader2 } from 'lucide-react';
import { useAdvocates, useClientOptions, useCreateCase } from '../hooks/useCases';
import { useAuth } from '../context/AuthContext';
import { canOpenCases } from '../lib/roles';
import { ApiError, errorMessage } from '../services/api/client';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { Button, ButtonLink } from '../components/ui/Button';
import { PageHeader } from '../components/ui/PageHeader';
import { ErrorState, LoadingState } from '../components/ui/QueryState';
import type {
  Advocate,
  CasePriority,
  CaseStatus,
  ClientOption,
  NewCaseInput,
  PracticeArea,
} from '../types';
import { validateNewCase, type NewCaseErrors, type NewCaseForm } from '../lib/validateNewCase';
import { todayIsoDate } from '../lib/format';
import { PRACTICE_AREAS, PRIORITIES, STATUSES } from '../lib/caseOptions';

/** Order in which fields appear, used to focus the first invalid one. */
const FIELD_ORDER: (keyof NewCaseForm)[] = [
  'title',
  'clientId',
  'practiceArea',
  'description',
  'leadAdvocateId',
  'opposingParty',
  'courtName',
  'nextHearing',
  'status',
  'priority',
];

function isFormField(name: string): name is keyof NewCaseForm {
  return (FIELD_ORDER as string[]).includes(name);
}

function BackLink() {
  return (
    <Link
      to="/app/cases"
      className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-brand-600 hover:text-brand-800"
    >
      <ArrowLeft className="h-4 w-4" aria-hidden="true" />
      Back to Cases
    </Link>
  );
}

export function NewCasePage() {
  const { user } = useAuth();
  const addedClient = (useLocation().state as { addedClient?: string } | null)?.addedClient;
  const mayOpen = canOpenCases(user);
  const clients = useClientOptions({ enabled: mayOpen });
  const advocates = useAdvocates();

  let body: ReactNode;
  if (!mayOpen) {
    body = (
      <Card className="px-6 py-10 text-center">
        <p role="status" className="text-sm text-brand-700">
          Opening a case is for administrators and advocates. An advocate can add you to a case
          team.
        </p>
        <ButtonLink to="/app/cases" variant="secondary" className="mt-4">
          Back to cases
        </ButtonLink>
      </Card>
    );
  } else if (clients.isPending || advocates.isPending) {
    body = (
      <Card>
        <LoadingState label="Loading clients and advocates…" />
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
    body = <NewCaseFormView clients={clients.data} advocates={advocates.data} />;
  }

  return (
    <>
      <BackLink />
      <PageHeader
        title="Add New Case"
        description="Open a new matter and add it to your case list."
      />
      {addedClient && (
        <p
          role="status"
          className="mb-4 rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-800 ring-1 ring-inset ring-emerald-600/20"
        >
          Added {addedClient}. Open their first case below; the client appears on your client list
          once you work on one of their cases.
        </p>
      )}
      {body}
    </>
  );
}

function NewCaseFormView({
  clients,
  advocates,
}: {
  clients: ClientOption[];
  advocates: Advocate[];
}) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const createCase = useCreateCase();
  const uid = useId();
  const [params] = useSearchParams();
  const preselected = params.get('client');
  const choosesLead = user?.role === 'Administrator';

  const [form, setForm] = useState<NewCaseForm>(() => ({
    title: '',
    // Opened from a client's page: that client, if it is one of the choices.
    clientId: clients.some((c) => c.id === preselected) ? (preselected ?? '') : '',
    practiceArea: 'Civil',
    status: 'Open',
    priority: 'Medium',
    // An Advocate leads the cases they open; an Administrator picks anyone.
    leadAdvocateId: (advocates.find((a) => a.id === user?.id) ?? advocates[0])?.id ?? '',
    courtName: '',
    opposingParty: '',
    nextHearing: '',
    description: '',
  }));
  const [errors, setErrors] = useState<NewCaseErrors>({});
  const [saveError, setSaveError] = useState<string | null>(null);

  const idFor = (key: keyof NewCaseForm) => `${uid}-${key}`;
  const errorIdFor = (key: keyof NewCaseForm) => `${uid}-${key}-error`;

  /** Accessibility wiring shared by every control. */
  const controlProps = (key: keyof NewCaseForm) => ({
    id: idFor(key),
    'aria-invalid': errors[key] ? true : undefined,
    'aria-describedby': errors[key] ? errorIdFor(key) : undefined,
  });

  const update = <K extends keyof NewCaseForm>(key: K, value: NewCaseForm[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => ({ ...prev, [key]: undefined }));
  };

  const showErrors = (found: NewCaseErrors): boolean => {
    setErrors(found);
    const firstInvalid = FIELD_ORDER.find((key) => found[key]);
    if (firstInvalid) document.getElementById(idFor(firstInvalid))?.focus();
    return firstInvalid !== undefined;
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (createCase.isPending) return;
    setSaveError(null);
    const found = validateNewCase(
      form,
      clients.map((c) => c.id),
      advocates.map((a) => a.id),
    );
    if (showErrors(found)) return;

    const input: NewCaseInput = {
      title: form.title,
      clientId: form.clientId,
      practiceArea: form.practiceArea,
      status: form.status,
      priority: form.priority,
      leadAdvocateId: form.leadAdvocateId,
      courtName: form.courtName || null,
      opposingParty: form.opposingParty || null,
      description: form.description,
      nextHearing: form.nextHearing || null,
    };

    createCase.mutate(input, {
      // Next step in the workflow: attach the case papers.
      onSuccess: (created) => navigate(`/app/cases/${created.id}?tab=documents`),
      onError: (error) => {
        // Server validation: show each message beside its field. The entered
        // values stay in the form either way.
        if (error instanceof ApiError && Object.keys(error.fieldErrors).length > 0) {
          const fromServer: NewCaseErrors = {};
          const other: string[] = [];
          for (const [field, message] of Object.entries(error.fieldErrors)) {
            if (isFormField(field)) fromServer[field] = message;
            else other.push(message);
          }
          showErrors(fromServer);
          if (other.length > 0) setSaveError(other.join(' '));
        } else {
          setSaveError(`The case was not created. ${errorMessage(error)}`);
        }
      },
    });
  };

  const errorCount = Object.values(errors).filter(Boolean).length;
  const saving = createCase.isPending;

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
                  ? 'One field needs attention before the case can be created.'
                  : `${errorCount} fields need attention before the case can be created.`}
              </p>
            )}
            {saveError && <p>{saveError}</p>}
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} noValidate aria-label="New case" aria-busy={saving}>
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <Card>
              <CardHeader title="Case Information" />
              <CardBody className="space-y-4">
                <Field
                  label="Case Title"
                  htmlFor={idFor('title')}
                  error={errors.title}
                  errorId={errorIdFor('title')}
                  required
                >
                  <input
                    {...controlProps('title')}
                    className="input-field"
                    placeholder="e.g. Aarav Textiles Pvt. Ltd. v. Meghdoot Logistics Pvt. Ltd."
                    value={form.title}
                    onChange={(e) => update('title', e.target.value)}
                    required
                  />
                </Field>

                <div className="grid gap-4 sm:grid-cols-2">
                  <Field
                    label="Client"
                    htmlFor={idFor('clientId')}
                    error={errors.clientId}
                    errorId={errorIdFor('clientId')}
                    required
                  >
                    <select
                      {...controlProps('clientId')}
                      className="input-field"
                      value={form.clientId}
                      onChange={(e) => update('clientId', e.target.value)}
                      required
                    >
                      <option value="">Select a client…</option>
                      {clients.map((client) => (
                        <option key={client.id} value={client.id}>
                          {client.name}
                          {client.isSample ? ' (sample)' : ''}
                        </option>
                      ))}
                    </select>
                  </Field>

                  <Field
                    label="Practice Area"
                    htmlFor={idFor('practiceArea')}
                    error={errors.practiceArea}
                    errorId={errorIdFor('practiceArea')}
                  >
                    <select
                      {...controlProps('practiceArea')}
                      className="input-field"
                      value={form.practiceArea}
                      onChange={(e) => update('practiceArea', e.target.value as PracticeArea)}
                    >
                      {PRACTICE_AREAS.map((area) => (
                        <option key={area}>{area}</option>
                      ))}
                    </select>
                  </Field>
                </div>

                <Field
                  label="Summary"
                  htmlFor={idFor('description')}
                  error={errors.description}
                  errorId={errorIdFor('description')}
                  required
                >
                  <textarea
                    {...controlProps('description')}
                    className="input-field min-h-[110px] resize-y"
                    placeholder="Briefly describe the matter, relief sought, and current posture."
                    value={form.description}
                    onChange={(e) => update('description', e.target.value)}
                    required
                  />
                </Field>
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="Parties & Court" />
              <CardBody className="grid gap-4 sm:grid-cols-2">
                <Field
                  label="Lead Advocate"
                  htmlFor={idFor('leadAdvocateId')}
                  error={errors.leadAdvocateId}
                  errorId={errorIdFor('leadAdvocateId')}
                >
                  <select
                    {...controlProps('leadAdvocateId')}
                    className="input-field"
                    value={form.leadAdvocateId}
                    onChange={(e) => update('leadAdvocateId', e.target.value)}
                    disabled={!choosesLead}
                  >
                    {advocates.length === 0 && <option value="">No advocates available</option>}
                    {advocates.map((advocate) => (
                      <option key={advocate.id} value={advocate.id}>
                        {advocate.name}
                      </option>
                    ))}
                  </select>
                  {!choosesLead && (
                    <p className="mt-1 text-xs text-brand-400">You lead the cases you open.</p>
                  )}
                </Field>

                <Field
                  label="Opposing Party"
                  htmlFor={idFor('opposingParty')}
                  error={errors.opposingParty}
                  errorId={errorIdFor('opposingParty')}
                >
                  <input
                    {...controlProps('opposingParty')}
                    className="input-field"
                    placeholder="e.g. Meghdoot Logistics Pvt. Ltd. / State (NCT of Delhi)"
                    value={form.opposingParty}
                    onChange={(e) => update('opposingParty', e.target.value)}
                  />
                </Field>

                <Field
                  label="Court / Forum"
                  htmlFor={idFor('courtName')}
                  error={errors.courtName}
                  errorId={errorIdFor('courtName')}
                >
                  <input
                    {...controlProps('courtName')}
                    className="input-field"
                    placeholder="e.g. High Court of Delhi at New Delhi"
                    value={form.courtName}
                    onChange={(e) => update('courtName', e.target.value)}
                  />
                </Field>

                <Field
                  label="Next Hearing Date"
                  htmlFor={idFor('nextHearing')}
                  error={errors.nextHearing}
                  errorId={errorIdFor('nextHearing')}
                >
                  <input
                    {...controlProps('nextHearing')}
                    type="date"
                    min={todayIsoDate()}
                    className="input-field"
                    value={form.nextHearing}
                    onChange={(e) => update('nextHearing', e.target.value)}
                  />
                </Field>
              </CardBody>
            </Card>
          </div>

          <div className="space-y-6">
            <Card>
              <CardHeader title="Classification" />
              <CardBody className="space-y-4">
                <Field
                  label="Status"
                  htmlFor={idFor('status')}
                  error={errors.status}
                  errorId={errorIdFor('status')}
                >
                  <select
                    {...controlProps('status')}
                    className="input-field"
                    value={form.status}
                    onChange={(e) => update('status', e.target.value as CaseStatus)}
                  >
                    {STATUSES.map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </select>
                </Field>

                <Field
                  label="Priority"
                  htmlFor={idFor('priority')}
                  error={errors.priority}
                  errorId={errorIdFor('priority')}
                >
                  <select
                    {...controlProps('priority')}
                    className="input-field"
                    value={form.priority}
                    onChange={(e) => update('priority', e.target.value as CasePriority)}
                  >
                    {PRIORITIES.map((p) => (
                      <option key={p}>{p}</option>
                    ))}
                  </select>
                </Field>
              </CardBody>
            </Card>

            <div className="flex flex-col gap-2">
              <Button type="submit" className="w-full" disabled={saving}>
                {saving ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Check className="h-4 w-4" aria-hidden="true" />
                )}
                {saving ? 'Creating case…' : 'Create Case'}
              </Button>
              <ButtonLink to="/app/cases" variant="secondary" className="w-full">
                Cancel
              </ButtonLink>
            </div>
          </div>
        </div>
      </form>
    </>
  );
}

function Field({
  label,
  htmlFor,
  error,
  errorId,
  required,
  children,
}: {
  label: string;
  htmlFor: string;
  error?: string;
  errorId?: string;
  required?: boolean;
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
      {error && (
        <p id={errorId} className="mt-1 text-xs text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}
