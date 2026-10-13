import { useId, useState, type FormEvent, type ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertCircle, ArrowLeft, Check } from 'lucide-react';
import { useCases } from '../context/CasesContext';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { Button, ButtonLink } from '../components/ui/Button';
import { PageHeader } from '../components/ui/PageHeader';
import type { CasePriority, CaseStatus, NewCaseInput, PracticeArea } from '../types';
import { validateNewCase, type NewCaseErrors, type NewCaseForm } from '../lib/validateNewCase';
import { todayIsoDate } from '../lib/format';

const PRACTICE_AREAS: PracticeArea[] = [
  'Corporate / Commercial',
  'Civil',
  'Criminal',
  'Family',
  'Intellectual Property',
  'Constitutional / Administrative',
  'Real Estate',
  'Employment & Labour',
];
const STATUSES: CaseStatus[] = ['Open', 'In Progress', 'On Hold', 'Closed'];
const PRIORITIES: CasePriority[] = ['Low', 'Medium', 'High', 'Critical'];

/** Order in which fields appear, used to focus the first invalid one. */
const FIELD_ORDER: (keyof NewCaseForm)[] = [
  'title',
  'clientId',
  'practiceArea',
  'description',
  'leadAttorney',
  'opposingParty',
  'courtName',
  'nextHearing',
  'status',
  'priority',
];

export function NewCasePage() {
  const { addCase, clients, advocates } = useCases();
  const navigate = useNavigate();
  const uid = useId();

  const [form, setForm] = useState<NewCaseForm>(() => ({
    title: '',
    clientId: '',
    practiceArea: 'Civil',
    status: 'Open',
    priority: 'Medium',
    leadAttorney: advocates[0] ?? '',
    courtName: '',
    opposingParty: '',
    nextHearing: '',
    description: '',
  }));
  const [errors, setErrors] = useState<NewCaseErrors>({});

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

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const found = validateNewCase(form, clients, advocates);
    setErrors(found);

    const firstInvalid = FIELD_ORDER.find((key) => found[key]);
    if (firstInvalid) {
      document.getElementById(idFor(firstInvalid))?.focus();
      return;
    }

    const input: NewCaseInput = {
      title: form.title,
      clientId: form.clientId,
      practiceArea: form.practiceArea,
      status: form.status,
      priority: form.priority,
      leadAttorney: form.leadAttorney,
      courtName: form.courtName,
      opposingParty: form.opposingParty,
      description: form.description,
      nextHearing: form.nextHearing || undefined,
    };

    const created = addCase(input);
    // Next step in the workflow: attach the case papers.
    navigate(`/app/cases/${created.id}?tab=documents`);
  };

  const errorCount = Object.values(errors).filter(Boolean).length;

  return (
    <>
      <Link
        to="/app/cases"
        className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-brand-600 hover:text-brand-800"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Cases
      </Link>

      <PageHeader
        title="Add New Case"
        description="Open a new matter and add it to your case list."
      />

      {errorCount > 0 && (
        <p
          role="alert"
          className="mb-4 flex items-center gap-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-inset ring-red-600/20"
        >
          <AlertCircle className="h-4 w-4 shrink-0" />
          {errorCount === 1
            ? 'One field needs attention before the case can be created.'
            : `${errorCount} fields need attention before the case can be created.`}
        </p>
      )}

      <form onSubmit={handleSubmit} noValidate aria-label="New case">
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
                        </option>
                      ))}
                    </select>
                  </Field>

                  <Field label="Practice Area" htmlFor={idFor('practiceArea')}>
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
                  htmlFor={idFor('leadAttorney')}
                  error={errors.leadAttorney}
                  errorId={errorIdFor('leadAttorney')}
                >
                  <select
                    {...controlProps('leadAttorney')}
                    className="input-field"
                    value={form.leadAttorney}
                    onChange={(e) => update('leadAttorney', e.target.value)}
                  >
                    {advocates.map((name) => (
                      <option key={name}>{name}</option>
                    ))}
                  </select>
                </Field>

                <Field label="Opposing Party" htmlFor={idFor('opposingParty')}>
                  <input
                    {...controlProps('opposingParty')}
                    className="input-field"
                    placeholder="e.g. Meghdoot Logistics Pvt. Ltd. / State (NCT of Delhi)"
                    value={form.opposingParty}
                    onChange={(e) => update('opposingParty', e.target.value)}
                  />
                </Field>

                <Field label="Court / Forum" htmlFor={idFor('courtName')}>
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
                <Field label="Status" htmlFor={idFor('status')}>
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

                <Field label="Priority" htmlFor={idFor('priority')}>
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
              <Button type="submit" className="w-full">
                <Check className="h-4 w-4" />
                Create Case
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
