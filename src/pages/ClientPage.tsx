import { useState, type ReactNode } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, FolderPlus, Pencil } from 'lucide-react';
import { useClient, useCreateClient, useUpdateClient } from '../hooks/useCases';
import { useDemoStatus } from '../hooks/useDemo';
import { useAuth } from '../context/AuthContext';
import { canOpenCases } from '../lib/roles';
import { ApiError } from '../services/api/client';
import { casePath, clientPath, CLIENTS_PATH, newCaseForClientPath } from '../lib/paths';
import { formatDate } from '../lib/format';
import type { ClientChanges, ClientDetail } from '../types';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { Button, ButtonLink } from '../components/ui/Button';
import { PageHeader } from '../components/ui/PageHeader';
import { ArchivedBadge, SampleBadge, StatusBadge } from '../components/ui/Badge';
import { ErrorState, LoadingState } from '../components/ui/QueryState';
import { ClientForm } from '../components/clients/ClientForm';
import { EMPTY_CLIENT, valuesOf, type ClientFormValues } from '../lib/clientForm';

function BackToClients() {
  return (
    <Link
      to={CLIENTS_PATH}
      className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-brand-600 hover:text-brand-800"
    >
      <ArrowLeft className="h-4 w-4" aria-hidden="true" />
      All Clients
    </Link>
  );
}

/** Adding a client (Administrators and Advocates). */
export function NewClientPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const create = useCreateClient();
  // Demo only: a fictional client, offered only in the verified demo database.
  const demo = useDemoStatus();
  const demoVerified = demo.data?.verified === true;
  const [fictional, setFictional] = useState(false);

  let body: ReactNode;
  if (!canOpenCases(user)) {
    body = (
      <Card className="px-6 py-10 text-center">
        <p role="status" className="text-sm text-brand-700">
          Adding clients is for administrators and advocates.
        </p>
      </Card>
    );
  } else {
    body = (
      <Card>
        <CardBody>
          {demoVerified && (
            <label className="mb-4 flex items-start gap-2 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900 ring-1 ring-inset ring-amber-600/30">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={fictional}
                onChange={(e) => setFictional(e.target.checked)}
              />
              <span>
                <strong>Fictional demo client.</strong> Stored as a sample record; only invented
                names and contact details.
              </span>
            </label>
          )}
          <ClientForm
            initial={EMPTY_CLIENT}
            label="New client"
            submitLabel="Add Client"
            busyLabel="Adding…"
            failurePrefix="The client was not added."
            onSubmit={async (values) => {
              const created = await create.mutateAsync({
                name: values.name,
                company: values.company || null,
                email: values.email,
                phone: values.phone,
                fictional: demoVerified && fictional,
              });
              // An Administrator sees every client; anyone else sees a client
              // through their cases, so they go on to open the first one.
              if (user?.role === 'Administrator') {
                navigate(clientPath(created.id), { state: { added: true } });
              } else {
                navigate(newCaseForClientPath(created.id), {
                  state: { addedClient: created.name },
                });
              }
            }}
            cancel={
              <ButtonLink to={CLIENTS_PATH} variant="secondary">
                Cancel
              </ButtonLink>
            }
          />
        </CardBody>
      </Card>
    );
  }
  return (
    <>
      <BackToClients />
      <PageHeader title="New Client" description="Add a client so you can open cases for them." />
      {body}
    </>
  );
}

/** A client's details and the cases of theirs you may see. */
export function ClientPage() {
  const { clientId = '' } = useParams<{ clientId: string }>();
  const client = useClient(clientId);
  const notFound = client.error instanceof ApiError && client.error.isNotFound;

  let body: ReactNode;
  if (client.isPending) {
    body = (
      <Card>
        <LoadingState label="Loading the client…" />
      </Card>
    );
  } else if (!client.data || notFound) {
    body = (
      <Card>
        <ErrorState
          title={notFound ? 'Client not found' : "Couldn't load the client"}
          error={client.error}
          onRetry={notFound ? undefined : () => client.refetch()}
        />
      </Card>
    );
  } else {
    body = <ClientView key={client.data.id} client={client.data} />;
  }
  return (
    <>
      <BackToClients />
      {body}
    </>
  );
}

function ClientView({ client: c }: { client: ClientDetail }) {
  const { user } = useAuth();
  const location = useLocation();
  const update = useUpdateClient(c.id);
  const [editing, setEditing] = useState(false);
  const [notice, setNotice] = useState<string | null>(
    (location.state as { added?: boolean } | null)?.added ? `Added ${c.name}.` : null,
  );

  const save = async (values: ClientFormValues) => {
    const before = valuesOf(c);
    const changes: ClientChanges = {};
    if (values.name.trim() !== before.name) changes.name = values.name;
    if (values.company.trim() !== before.company) changes.company = values.company || null;
    if (values.email.trim() !== before.email) changes.email = values.email;
    if (values.phone.trim() !== before.phone) changes.phone = values.phone;
    if (Object.keys(changes).length > 0) await update.mutateAsync(changes);
    setEditing(false);
    setNotice(Object.keys(changes).length > 0 ? 'Client details saved.' : null);
  };

  return (
    <>
      <PageHeader
        title={c.name}
        description={c.company ?? undefined}
        actions={
          <div className="flex gap-2">
            {c.canEdit && !editing && (
              <Button
                variant="secondary"
                onClick={() => {
                  setNotice(null);
                  setEditing(true);
                }}
              >
                <Pencil className="h-4 w-4" aria-hidden="true" />
                Edit details
              </Button>
            )}
            {canOpenCases(user) && (
              <ButtonLink to={newCaseForClientPath(c.id)}>
                <FolderPlus className="h-4 w-4" aria-hidden="true" />
                Open a case
              </ButtonLink>
            )}
          </div>
        }
      />
      <div aria-live="polite">
        {notice && (
          <p className="mb-4 rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-800 ring-1 ring-inset ring-emerald-600/20">
            {notice}
          </p>
        )}
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader title="Contact Details" />
          <CardBody>
            {editing ? (
              <ClientForm
                initial={valuesOf(c)}
                label="Edit client"
                submitLabel="Save"
                busyLabel="Saving…"
                failurePrefix="The changes were not saved."
                onSubmit={save}
                cancel={
                  <Button variant="secondary" onClick={() => setEditing(false)}>
                    Cancel
                  </Button>
                }
              />
            ) : (
              <dl className="space-y-3 text-sm">
                <div>
                  <dt className="text-xs uppercase tracking-wide text-brand-400">E-mail</dt>
                  <dd className="text-brand-800">{c.email}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-brand-400">Phone</dt>
                  <dd className="text-brand-800">{c.phone}</dd>
                </div>
                {c.isSample && (
                  <div>
                    <SampleBadge />
                  </div>
                )}
              </dl>
            )}
          </CardBody>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader title={`Cases (${c.cases.length})`} />
          <CardBody className="p-0">
            {c.cases.length === 0 ? (
              <p className="px-5 py-6 text-sm text-brand-500">No cases yet.</p>
            ) : (
              <ul className="divide-y divide-brand-100" aria-label="Client's cases">
                {c.cases.map((k) => (
                  <li key={k.id} className="flex items-center justify-between gap-3 px-5 py-3">
                    <div>
                      <Link
                        to={casePath(k.id)}
                        className="text-sm font-medium text-brand-900 hover:text-brand-700"
                      >
                        {k.title}
                      </Link>
                      <p className="text-xs text-brand-500">
                        {k.caseNumber} · {k.leadAttorney} · Opened {formatDate(k.openedOn)}
                      </p>
                    </div>
                    <div className="flex shrink-0 gap-1.5">
                      {k.archivedAt && <ArchivedBadge />}
                      <StatusBadge status={k.status} />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
      </div>
    </>
  );
}
