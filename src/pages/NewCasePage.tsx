import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, Check } from 'lucide-react';
import { useCases } from '../context/CasesContext';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { PageHeader } from '../components/ui/PageHeader';
import { mockClients, advocates } from '../data/mockData';
import type {
  CasePriority,
  CaseStatus,
  NewCaseInput,
  PracticeArea,
} from '../types';

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

type FormState = {
  title: string;
  clientId: string;
  practiceArea: PracticeArea;
  status: CaseStatus;
  priority: CasePriority;
  leadAttorney: string;
  courtName: string;
  opposingParty: string;
  nextHearing: string;
  description: string;
};

const initialState: FormState = {
  title: '',
  clientId: mockClients[0].id,
  practiceArea: 'Civil',
  status: 'Open',
  priority: 'Medium',
  leadAttorney: advocates[0],
  courtName: '',
  opposingParty: '',
  nextHearing: '',
  description: '',
};

export function NewCasePage() {
  const { addCase } = useCases();
  const navigate = useNavigate();

  const [form, setForm] = useState<FormState>(initialState);
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({});

  const update = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => ({ ...prev, [key]: undefined }));
  };

  const validate = (): boolean => {
    const next: Partial<Record<keyof FormState, string>> = {};
    if (form.title.trim().length < 4) {
      next.title = 'Enter a descriptive case title (at least 4 characters).';
    }
    if (!form.clientId) next.clientId = 'Select a client.';
    if (form.description.trim().length < 10) {
      next.description = 'Provide a short summary (at least 10 characters).';
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

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
    navigate(`/app/cases/${created.id}`);
  };

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

      <form onSubmit={handleSubmit} noValidate>
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <Card>
              <CardHeader title="Case Information" />
              <CardBody className="space-y-4">
                <Field label="Case Title" error={errors.title} required>
                  <input
                    className="input-field"
                    placeholder="e.g. Aarav Textiles Pvt. Ltd. v. Meghdoot Logistics Pvt. Ltd."
                    value={form.title}
                    onChange={(e) => update('title', e.target.value)}
                  />
                </Field>

                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Client" error={errors.clientId} required>
                    <select
                      className="input-field"
                      value={form.clientId}
                      onChange={(e) => update('clientId', e.target.value)}
                    >
                      {mockClients.map((client) => (
                        <option key={client.id} value={client.id}>
                          {client.name}
                        </option>
                      ))}
                    </select>
                  </Field>

                  <Field label="Practice Area">
                    <select
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

                <Field label="Summary" error={errors.description} required>
                  <textarea
                    className="input-field min-h-[110px] resize-y"
                    placeholder="Briefly describe the matter, relief sought, and current posture."
                    value={form.description}
                    onChange={(e) => update('description', e.target.value)}
                  />
                </Field>
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="Parties & Court" />
              <CardBody className="grid gap-4 sm:grid-cols-2">
                <Field label="Lead Advocate">
                  <select
                    className="input-field"
                    value={form.leadAttorney}
                    onChange={(e) => update('leadAttorney', e.target.value)}
                  >
                    {advocates.map((name) => (
                      <option key={name}>{name}</option>
                    ))}
                  </select>
                </Field>

                <Field label="Opposing Party">
                  <input
                    className="input-field"
                    placeholder="e.g. Meghdoot Logistics Pvt. Ltd. / State (NCT of Delhi)"
                    value={form.opposingParty}
                    onChange={(e) => update('opposingParty', e.target.value)}
                  />
                </Field>

                <Field label="Court / Forum">
                  <input
                    className="input-field"
                    placeholder="e.g. High Court of Delhi at New Delhi"
                    value={form.courtName}
                    onChange={(e) => update('courtName', e.target.value)}
                  />
                </Field>

                <Field label="Next Hearing Date">
                  <input
                    type="date"
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
                <Field label="Status">
                  <select
                    className="input-field"
                    value={form.status}
                    onChange={(e) => update('status', e.target.value as CaseStatus)}
                  >
                    {STATUSES.map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </select>
                </Field>

                <Field label="Priority">
                  <select
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
              <Link to="/app/cases" className="w-full">
                <Button type="button" variant="secondary" className="w-full">
                  Cancel
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </form>
    </>
  );
}

function Field({
  label,
  error,
  required,
  children,
}: {
  label: string;
  error?: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="label-text">
        {label}
        {required && <span className="ml-0.5 text-red-500">*</span>}
      </label>
      {children}
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  );
}
