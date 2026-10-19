import { screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { renderApp } from '../test/renderApp';
import {
  ARYAN_EMAIL,
  MOCK_PARALEGAL_EMAIL,
  mockAddMember,
  mockAddUser,
  mockApiState,
  server,
} from '../test/mockApi';

// Client records. The server enforces who sees and changes what
// (server/tests/test_clients.py); these tests check what the screens offer.

const SATTVIK = 'case-1005';
const sattvikClient = () => {
  const c = mockApiState().cases.find((k) => k.id === SATTVIK);
  const client = mockApiState().clients.find((x) => x.id === c?.clientId);
  if (!client) throw new Error('the Sattvik case has a client');
  return client;
};

function capture(method: string): unknown[] {
  const bodies: unknown[] = [];
  server.events.on('request:start', ({ request }) => {
    if (request.method === method && new URL(request.url).pathname.startsWith('/api/clients')) {
      void request
        .clone()
        .json()
        .then((b) => bodies.push(b));
    }
  });
  return bodies;
}

afterEach(() => server.events.removeAllListeners());

describe('clients', () => {
  it('lets an Administrator find a client and change one detail', async () => {
    const client = sattvikClient();
    const patches = capture('PATCH');
    const { user } = renderApp('/app/clients');

    const rows = await screen.findAllByRole('row');
    expect(rows.length - 1).toBe(mockApiState().clients.length);
    await user.type(screen.getByLabelText('Search clients'), client.name.slice(0, 6));
    await user.click(screen.getByRole('link', { name: new RegExp(client.name) }));

    expect(await screen.findByRole('heading', { level: 1, name: client.name })).toBeVisible();
    expect(
      within(screen.getByRole('list', { name: "Client's cases" })).getByRole('link'),
    ).toHaveAttribute('href', `/app/cases/${SATTVIK}`);
    await user.click(screen.getByRole('button', { name: 'Edit details' }));
    const phone = screen.getByLabelText(/Phone/);
    await user.clear(phone);
    await user.type(phone, '+91 00000 22222');
    await user.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText('Client details saved.')).toBeVisible();
    expect(screen.getByText('+91 00000 22222')).toBeVisible();
    expect(patches).toEqual([{ phone: '+91 00000 22222' }]);
  });

  it('lets an Advocate add a client and open a case for them', async () => {
    const { user, url } = renderApp('/app/clients', { as: ARYAN_EMAIL });
    const rows = await screen.findAllByRole('row');
    expect(rows).toHaveLength(2); // only the client of the case he leads

    await user.click(screen.getByRole('link', { name: /New Client/ }));
    await user.type(await screen.findByLabelText(/Name/), 'Example Traders LLP');
    await user.type(screen.getByLabelText(/E-mail/), 'accounts@traders.example');
    await user.type(screen.getByLabelText(/Phone/), '+91 00000 11111');
    await user.click(screen.getByRole('button', { name: 'Add Client' }));

    // He sees clients through his cases, so he goes on to open the first one.
    await waitFor(() => expect(url()).toMatch(/^\/app\/cases\/new\?client=/));
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Added Example Traders LLP. Open their first case below',
    );
    expect(await screen.findByLabelText(/Client/)).toHaveDisplayValue('Example Traders LLP');
  });

  it('checks the details before sending them', async () => {
    const posts = capture('POST');
    const { user } = renderApp('/app/clients/new');
    await user.type(await screen.findByLabelText(/Name/), 'Example Traders LLP');
    await user.type(screen.getByLabelText(/E-mail/), 'not-an-address');
    await user.type(screen.getByLabelText(/Phone/), '+91 00000 11111');
    await user.click(screen.getByRole('button', { name: 'Add Client' }));

    const email = screen.getByLabelText(/E-mail/);
    expect(email).toHaveAccessibleDescription('Enter an e-mail address such as name@example.com.');
    expect(email).toHaveFocus();
    expect(posts).toEqual([]);
  });

  it('shows a Paralegal the client without ways to change it', async () => {
    mockAddMember(SATTVIK, MOCK_PARALEGAL_EMAIL, 'paralegal');
    const client = sattvikClient();
    renderApp(`/app/clients/${client.id}`, { as: MOCK_PARALEGAL_EMAIL });

    expect(await screen.findByRole('heading', { level: 1, name: client.name })).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Edit details' })).toBeNull();
    expect(screen.queryByRole('link', { name: 'Open a case' })).toBeNull();
  });

  it('tells a Paralegal that adding clients is for advocates', async () => {
    renderApp('/app/clients/new', { as: MOCK_PARALEGAL_EMAIL });
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Adding clients is for administrators and advocates.',
    );
    expect(screen.queryByRole('form')).toBeNull();
  });

  it('reports a client of someone else as not found', async () => {
    const outsider = 'rajat.deshpande@lexflow.test';
    mockAddUser({ email: outsider, role: 'Advocate', name: 'Rajat Deshpande' });
    renderApp(`/app/clients/${sattvikClient().id}`, { as: outsider });
    expect(await screen.findByText('Client not found')).toBeVisible();
  });
});
