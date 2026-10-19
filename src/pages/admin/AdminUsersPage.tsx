import { useId, useState, type FormEvent } from 'react';
import { KeyRound, Loader2, Lock, Pencil, UserPlus } from 'lucide-react';
import {
  useAdminUsers,
  useCreateUser,
  useResetPassword,
  useUpdateUser,
  useUserAction,
} from '../../hooks/useAdmin';
import { useClientOptions } from '../../hooks/useCases';
import { useAuth } from '../../context/AuthContext';
import { ApiError, errorMessage } from '../../services/api/client';
import { formatDate } from '../../lib/format';
import type { AdminUser, UserRole } from '../../types';
import { PageHeader } from '../../components/ui/PageHeader';
import { AdminNav } from '../../components/admin/AdminNav';
import { Card, CardBody, CardHeader } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Field } from '../../components/ui/Field';
import { ErrorState, LoadingState } from '../../components/ui/QueryState';
import { errorId, fieldProps } from '../../lib/fields';

const ROLES: UserRole[] = ['Administrator', 'Advocate', 'Paralegal', 'Client'];
const MIN_PASSWORD = 12;

/** Account administration (Administrators only; the server refuses anyone else). */
export function AdminUsersPage() {
  const { user } = useAuth();
  if (user?.role !== 'Administrator') {
    return (
      <Card className="px-6 py-10 text-center">
        <p role="status" className="text-sm text-brand-700">
          Account administration is for administrators.
        </p>
      </Card>
    );
  }
  return <Accounts myId={user.id} />;
}

function Accounts({ myId }: { myId: string }) {
  const users = useAdminUsers();
  const [adding, setAdding] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  return (
    <>
      <PageHeader
        title="Accounts"
        description="Who can sign in. There is no self-registration: accounts are created here or from the command line."
        actions={
          !adding && (
            <Button
              onClick={() => {
                setNotice(null);
                setAdding(true);
              }}
            >
              <UserPlus className="h-4 w-4" aria-hidden="true" />
              New Account
            </Button>
          )
        }
      />
      <AdminNav />
      <div aria-live="polite">
        {notice && (
          <p className="mb-4 rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-800 ring-1 ring-inset ring-emerald-600/20">
            {notice}
          </p>
        )}
      </div>
      {adding && (
        <NewAccount
          onDone={(message) => {
            setAdding(false);
            if (message) setNotice(message);
          }}
        />
      )}
      {users.isPending ? (
        <Card>
          <LoadingState label="Loading accounts…" />
        </Card>
      ) : !users.data ? (
        <Card>
          <ErrorState
            title="Couldn't load the accounts"
            error={users.error}
            onRetry={() => users.refetch()}
          />
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <ul className="divide-y divide-brand-100" aria-label="Accounts">
            {users.data.map((u) => (
              <AccountRow key={u.id} account={u} isMe={u.id === myId} onNotice={setNotice} />
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}

function status(u: AdminUser): string {
  if (!u.isActive) return 'Disabled';
  if (u.isLocked) return 'Locked after failed sign-ins';
  if (!u.canSignIn) return 'No password yet';
  if (u.mustChangePassword) return 'Must choose a new password';
  return 'Active';
}

function AccountRow({
  account: u,
  isMe,
  onNotice,
}: {
  account: AdminUser;
  isMe: boolean;
  onNotice: (message: string) => void;
}) {
  const action = useUserAction();
  const [mode, setMode] = useState<'view' | 'edit' | 'password'>('view');
  const [failure, setFailure] = useState<string | null>(null);

  const run = (kind: 'disable' | 'enable' | 'unlock', done: string) => {
    setFailure(null);
    action.mutate(
      { id: u.id, action: kind },
      {
        onSuccess: () => onNotice(done),
        onError: (error) => setFailure(errorMessage(error)),
      },
    );
  };

  return (
    <li className="px-5 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-brand-900">
            {u.name}
            {isMe && <span className="ml-1 text-xs text-brand-500">(you)</span>}
          </p>
          <p className="text-xs text-brand-500">
            {u.email ?? 'no e-mail address'} · {u.role}
            {u.clientName && ` for ${u.clientName}`}
          </p>
          <p className="text-xs text-brand-500">
            {status(u)}
            {u.lastLoginAt && ` · Last sign-in ${formatDate(u.lastLoginAt.slice(0, 10))}`}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Button
            variant="ghost"
            size="sm"
            aria-label={`Edit ${u.name}`}
            onClick={() => setMode(mode === 'edit' ? 'view' : 'edit')}
          >
            <Pencil className="h-4 w-4" aria-hidden="true" />
          </Button>
          {!isMe && u.email && (
            <Button
              variant="ghost"
              size="sm"
              aria-label={`Set a temporary password for ${u.name}`}
              onClick={() => setMode(mode === 'password' ? 'view' : 'password')}
            >
              <KeyRound className="h-4 w-4" aria-hidden="true" />
            </Button>
          )}
          {u.isLocked && (
            <Button
              variant="secondary"
              size="sm"
              disabled={action.isPending}
              onClick={() => run('unlock', `Unlocked ${u.name}.`)}
            >
              <Lock className="h-4 w-4" aria-hidden="true" />
              Unlock
            </Button>
          )}
          {!isMe &&
            (u.isActive ? (
              <Button
                variant="secondary"
                size="sm"
                disabled={action.isPending}
                onClick={() =>
                  run('disable', `Disabled ${u.name}: they are signed out and cannot sign in.`)
                }
              >
                Disable
              </Button>
            ) : (
              <Button
                variant="secondary"
                size="sm"
                disabled={action.isPending}
                onClick={() => run('enable', `Enabled ${u.name}.`)}
              >
                Enable
              </Button>
            ))}
        </div>
      </div>
      {failure && (
        <p role="alert" className="mt-2 text-sm text-red-600">
          {failure}
        </p>
      )}
      {mode === 'edit' && (
        <EditAccount
          account={u}
          onDone={(message) => {
            setMode('view');
            if (message) onNotice(message);
          }}
        />
      )}
      {mode === 'password' && (
        <ResetPassword
          account={u}
          onDone={(message) => {
            setMode('view');
            if (message) onNotice(message);
          }}
        />
      )}
    </li>
  );
}

function serverErrors(error: unknown): Record<string, string> | null {
  return error instanceof ApiError && Object.keys(error.fieldErrors).length > 0
    ? error.fieldErrors
    : null;
}

function NewAccount({ onDone }: { onDone: (message: string | null) => void }) {
  const create = useCreateUser();
  const clients = useClientOptions();
  const uid = useId();
  const [form, setForm] = useState({
    name: '',
    email: '',
    role: 'Advocate' as UserRole,
    clientId: '',
    temporaryPassword: '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [failure, setFailure] = useState<string | null>(null);
  const set = (field: keyof typeof form, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: '' }));
  };
  const props = (field: string) => fieldProps(uid, field, errors[field] || undefined);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setFailure(null);
    const found: Record<string, string> = {};
    if (form.name.trim().length < 2) found.name = "Enter the person's name (2 to 200 characters).";
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email.trim())) {
      found.email = 'Enter an e-mail address such as name@example.com.';
    }
    if (form.role === 'Client' && !form.clientId) {
      found.clientId = 'Choose the client this account represents.';
    }
    if (form.temporaryPassword.length < MIN_PASSWORD) {
      found.temporaryPassword = `Use at least ${MIN_PASSWORD} characters.`;
    }
    setErrors(found);
    const first = ['name', 'email', 'clientId', 'temporaryPassword'].find((f) => found[f]);
    if (first) {
      document.getElementById(`${uid}-${first}`)?.focus();
      return;
    }
    create.mutate(
      {
        name: form.name,
        email: form.email,
        role: form.role,
        clientId: form.role === 'Client' ? form.clientId : null,
        temporaryPassword: form.temporaryPassword,
      },
      {
        onSuccess: (created) =>
          onDone(
            `Created ${created.name}. Give them the temporary password in person; they choose their own at first sign-in.`,
          ),
        onError: (error) => {
          const fromServer = serverErrors(error);
          if (fromServer) setErrors(fromServer);
          else setFailure(`The account was not created. ${errorMessage(error)}`);
        },
      },
    );
  };

  return (
    <Card className="mb-4">
      <CardHeader title="New Account" />
      <CardBody>
        <form onSubmit={submit} noValidate aria-label="New account">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              label="Name"
              htmlFor={`${uid}-name`}
              error={errors.name || undefined}
              errorId={errorId(uid, 'name')}
              required
            >
              <input
                {...props('name')}
                className="input-field"
                value={form.name}
                onChange={(e) => set('name', e.target.value)}
              />
            </Field>
            <Field
              label="E-mail"
              htmlFor={`${uid}-email`}
              error={errors.email || undefined}
              errorId={errorId(uid, 'email')}
              required
            >
              <input
                {...props('email')}
                type="email"
                autoComplete="off"
                className="input-field"
                value={form.email}
                onChange={(e) => set('email', e.target.value)}
              />
            </Field>
            <Field label="Role" htmlFor={`${uid}-role`}>
              <select
                id={`${uid}-role`}
                className="input-field"
                value={form.role}
                onChange={(e) => set('role', e.target.value)}
              >
                {ROLES.map((r) => (
                  <option key={r}>{r}</option>
                ))}
              </select>
            </Field>
            {form.role === 'Client' && (
              <Field
                label="Client represented"
                htmlFor={`${uid}-clientId`}
                error={errors.clientId || undefined}
                errorId={errorId(uid, 'clientId')}
                required
              >
                <select
                  {...props('clientId')}
                  className="input-field"
                  value={form.clientId}
                  onChange={(e) => set('clientId', e.target.value)}
                >
                  <option value="">Select a client…</option>
                  {(clients.data ?? []).map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            <Field
              label="Temporary password"
              htmlFor={`${uid}-temporaryPassword`}
              error={errors.temporaryPassword || undefined}
              errorId={errorId(uid, 'temporaryPassword')}
              hint={`At least ${MIN_PASSWORD} characters. They must replace it at first sign-in.`}
              required
            >
              <input
                {...props('temporaryPassword')}
                type="password"
                autoComplete="new-password"
                className="input-field"
                value={form.temporaryPassword}
                onChange={(e) => set('temporaryPassword', e.target.value)}
              />
            </Field>
          </div>
          {failure && (
            <p role="alert" className="mt-3 text-sm text-red-600">
              {failure}
            </p>
          )}
          <div className="mt-4 flex gap-2">
            <Button type="submit" disabled={create.isPending}>
              {create.isPending && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
              Create Account
            </Button>
            <Button variant="secondary" onClick={() => onDone(null)}>
              Cancel
            </Button>
          </div>
        </form>
      </CardBody>
    </Card>
  );
}

function EditAccount({
  account: u,
  onDone,
}: {
  account: AdminUser;
  onDone: (message: string | null) => void;
}) {
  const update = useUpdateUser();
  const uid = useId();
  const [name, setName] = useState(u.name);
  const [email, setEmail] = useState(u.email ?? '');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [failure, setFailure] = useState<string | null>(null);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const changes: { name?: string; email?: string } = {};
    if (name.trim() !== u.name) changes.name = name;
    if (email.trim() !== (u.email ?? '')) changes.email = email;
    if (Object.keys(changes).length === 0) {
      onDone(null);
      return;
    }
    update.mutate(
      { id: u.id, changes },
      {
        onSuccess: () => onDone('Account details saved.'),
        onError: (error) => {
          const fromServer = serverErrors(error);
          if (fromServer) setErrors(fromServer);
          else setFailure(errorMessage(error));
        },
      },
    );
  };

  return (
    <form
      onSubmit={submit}
      noValidate
      aria-label={`Edit ${u.name}`}
      className="mt-3 grid gap-3 sm:grid-cols-3"
    >
      <Field
        label="Name"
        htmlFor={`${uid}-name`}
        error={errors.name}
        errorId={errorId(uid, 'name')}
      >
        <input
          {...fieldProps(uid, 'name', errors.name)}
          className="input-field"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </Field>
      <Field
        label="E-mail"
        htmlFor={`${uid}-email`}
        error={errors.email}
        errorId={errorId(uid, 'email')}
      >
        <input
          {...fieldProps(uid, 'email', errors.email)}
          type="email"
          className="input-field"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </Field>
      <div className="flex items-end gap-2">
        <Button type="submit" size="sm" disabled={update.isPending}>
          Save
        </Button>
        <Button variant="ghost" size="sm" onClick={() => onDone(null)}>
          Cancel
        </Button>
      </div>
      {failure && (
        <p role="alert" className="text-sm text-red-600 sm:col-span-3">
          {failure}
        </p>
      )}
    </form>
  );
}

function ResetPassword({
  account: u,
  onDone,
}: {
  account: AdminUser;
  onDone: (message: string | null) => void;
}) {
  const reset = useResetPassword();
  const uid = useId();
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (password.length < MIN_PASSWORD) {
      setError(`Use at least ${MIN_PASSWORD} characters.`);
      document.getElementById(`${uid}-temporaryPassword`)?.focus();
      return;
    }
    reset.mutate(
      { id: u.id, password },
      {
        onSuccess: () =>
          onDone(
            `${u.name} has a temporary password: they are signed out everywhere and must choose a new one at next sign-in.`,
          ),
        onError: (err) => setError(serverErrors(err)?.temporaryPassword ?? errorMessage(err)),
      },
    );
  };

  return (
    <form
      onSubmit={submit}
      noValidate
      aria-label={`Temporary password for ${u.name}`}
      className="mt-3 flex flex-wrap items-end gap-2"
    >
      <Field
        label="Temporary password"
        htmlFor={`${uid}-temporaryPassword`}
        error={error ?? undefined}
        errorId={errorId(uid, 'temporaryPassword')}
      >
        <input
          {...fieldProps(uid, 'temporaryPassword', error ?? undefined)}
          type="password"
          autoComplete="new-password"
          className="input-field"
          value={password}
          onChange={(e) => {
            setPassword(e.target.value);
            setError(null);
          }}
        />
      </Field>
      <Button type="submit" size="sm" disabled={reset.isPending}>
        Set temporary password
      </Button>
      <Button variant="ghost" size="sm" onClick={() => onDone(null)}>
        Cancel
      </Button>
    </form>
  );
}
