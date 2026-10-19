import { useId, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Search, Users } from 'lucide-react';
import { useClients } from '../hooks/useCases';
import { useAuth } from '../context/AuthContext';
import { canOpenCases } from '../lib/roles';
import { clientPath, NEW_CLIENT_PATH } from '../lib/paths';
import { PageHeader } from '../components/ui/PageHeader';
import { Card } from '../components/ui/Card';
import { ButtonLink } from '../components/ui/Button';
import { SampleBadge } from '../components/ui/Badge';
import { ErrorState, LoadingState, StaleDataNotice } from '../components/ui/QueryState';

/** Clients you may see: all for Administrators, otherwise those of your cases. */
export function ClientsPage() {
  const { data: clients, isPending, isError, error, refetch } = useClients();
  const { user } = useAuth();
  const mayAdd = canOpenCases(user);
  const [query, setQuery] = useState('');
  const searchId = useId();

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (clients ?? []).filter(
      (c) =>
        q === '' ||
        c.name.toLowerCase().includes(q) ||
        (c.company ?? '').toLowerCase().includes(q) ||
        c.email.toLowerCase().includes(q),
    );
  }, [clients, query]);

  return (
    <>
      <PageHeader
        title="Clients"
        description={
          user?.role === 'Administrator'
            ? 'Every client of the firm.'
            : 'The clients of the cases you work on.'
        }
        actions={
          mayAdd && (
            <ButtonLink to={NEW_CLIENT_PATH}>
              <Plus className="h-4 w-4" aria-hidden="true" />
              New Client
            </ButtonLink>
          )
        }
      />
      {isError && clients && (
        <StaleDataNotice error={error} onRetry={() => refetch()} className="mb-4" />
      )}
      {isPending ? (
        <Card>
          <LoadingState label="Loading clients…" />
        </Card>
      ) : !clients ? (
        <Card>
          <ErrorState title="Couldn't load the clients" error={error} onRetry={() => refetch()} />
        </Card>
      ) : clients.length === 0 ? (
        <Card className="flex flex-col items-center px-6 py-16 text-center">
          <Users className="h-10 w-10 text-brand-300" strokeWidth={1.5} aria-hidden="true" />
          <p className="mt-3 text-sm font-medium text-brand-700">No clients to show</p>
          <p className="mt-1 text-sm text-brand-500">
            Clients appear here once you work on one of their cases.
          </p>
        </Card>
      ) : (
        <>
          <Card className="mb-4 p-4">
            <div className="relative w-full sm:max-w-xs">
              <label htmlFor={searchId} className="sr-only">
                Search clients
              </label>
              <Search
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-brand-400"
                aria-hidden="true"
              />
              <input
                id={searchId}
                type="search"
                placeholder="Search clients…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="input-field pl-9"
              />
            </div>
          </Card>
          <Card className="overflow-hidden">
            {filtered.length === 0 ? (
              <p className="px-5 py-10 text-center text-sm text-brand-500">No matching clients.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-left text-sm">
                  <thead>
                    <tr className="border-b border-brand-100 bg-brand-50/60 text-xs uppercase tracking-wide text-brand-500">
                      <th className="px-5 py-3 font-semibold">Client</th>
                      <th className="px-5 py-3 font-semibold">E-mail</th>
                      <th className="px-5 py-3 font-semibold">Phone</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-brand-100">
                    {filtered.map((c) => (
                      <tr key={c.id} className="hover:bg-brand-50/60">
                        <td className="px-5 py-3.5">
                          <Link to={clientPath(c.id)} className="block">
                            <span className="font-medium text-brand-900">{c.name}</span>
                            <span className="mt-0.5 flex items-center gap-2 text-xs text-brand-500">
                              {c.company}
                              {c.isSample && <SampleBadge />}
                            </span>
                          </Link>
                        </td>
                        <td className="px-5 py-3.5 text-brand-700">{c.email}</td>
                        <td className="px-5 py-3.5 text-brand-700">{c.phone}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </>
  );
}
