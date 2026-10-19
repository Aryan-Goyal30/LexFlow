import { screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { renderApp } from '../../test/renderApp';
import { ARYAN_EMAIL, mockApiState, server } from '../../test/mockApi';
import type { AuditEvent } from '../../types';

// Account administration. The server enforces it (server/tests/test_admin_users.py).

const TEMPORARY = 'a temporary passphrase 42';

function requests(): { method: string; path: string; body: string }[] {
  const seen: { method: string; path: string; body: string }[] = [];
  server.events.on('request:start', ({ request }) => {
    const path = new URL(request.url).pathname;
    if (path.startsWith('/api/admin')) {
      void request
        .clone()
        .text()
        .then((body) => seen.push({ method: request.method, path, body }));
    }
  });
  return seen;
}

afterEach(() => server.events.removeAllListeners());

const row = (name: string) =>
  within(screen.getByRole('list', { name: 'Accounts' }))
    .getByText(name, { exact: false, selector: 'p' })
    .closest('li') as HTMLElement;

describe('account administration', () => {
  it('is not offered to other roles', async () => {
    renderApp('/app/admin/users', { as: ARYAN_EMAIL });
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Account administration is for administrators.',
    );
    expect(screen.queryByRole('link', { name: /Administration/ })).toBeNull();
  });

  it('creates an account with a temporary password the person must replace', async () => {
    const seen = requests();
    const { user } = renderApp('/app/cases');
    await user.click(await screen.findByRole('link', { name: /Administration/ }));
    await user.click(await screen.findByRole('button', { name: /New Account/ }));
    const form = screen.getByRole('form', { name: 'New account' });
    await user.type(within(form).getByLabelText(/Name/), 'Meera Iyer');
    await user.type(within(form).getByLabelText(/E-mail/), 'meera.iyer@lexflow.test');
    await user.selectOptions(within(form).getByLabelText('Role'), 'Paralegal');
    await user.type(within(form).getByLabelText(/Temporary password/), TEMPORARY);
    await user.click(within(form).getByRole('button', { name: 'Create Account' }));

    expect(await screen.findByText(/^Created Meera Iyer\./)).toBeVisible();
    await waitFor(() => expect(row('Meera Iyer')).toHaveTextContent('Must choose a new password'));
    const created = mockApiState().users.find((u) => u.email === 'meera.iyer@lexflow.test');
    expect(created?.mustChangePassword).toBe(true);
    // The password went to the server once, and is shown nowhere.
    expect(seen.filter((r) => r.body.includes(TEMPORARY))).toHaveLength(1);
    expect(document.body.textContent).not.toContain(TEMPORARY);
  });

  it('checks a new account before sending it', async () => {
    const seen = requests();
    const { user } = renderApp('/app/admin/users');
    await user.click(await screen.findByRole('button', { name: /New Account/ }));
    const form = screen.getByRole('form', { name: 'New account' });
    await user.type(within(form).getByLabelText(/Name/), 'Meera Iyer');
    await user.type(within(form).getByLabelText(/E-mail/), 'meera.iyer@lexflow.test');
    await user.selectOptions(within(form).getByLabelText('Role'), 'Client');
    await user.type(within(form).getByLabelText(/Temporary password/), 'short');
    await user.click(within(form).getByRole('button', { name: 'Create Account' }));

    expect(within(form).getByLabelText(/Client represented/)).toHaveAccessibleDescription(
      'Choose the client this account represents.',
    );
    expect(within(form).getByLabelText(/Temporary password/)).toHaveAccessibleDescription(
      'Use at least 12 characters.',
    );
    expect(seen.filter((r) => r.method === 'POST')).toEqual([]);
  });

  it('disables and enables another account, but never your own', async () => {
    const { user } = renderApp('/app/admin/users');
    await screen.findByRole('list', { name: 'Accounts' });

    const mine = row('Test Administrator');
    expect(within(mine).queryByRole('button', { name: 'Disable' })).toBeNull();
    expect(within(mine).queryByRole('button', { name: /temporary password/ })).toBeNull();

    await user.click(within(row('Aryan Goyal')).getByRole('button', { name: 'Disable' }));
    expect(
      await screen.findByText('Disabled Aryan Goyal: they are signed out and cannot sign in.'),
    ).toBeVisible();
    await waitFor(() => expect(row('Aryan Goyal')).toHaveTextContent('Disabled'));
    await user.click(within(row('Aryan Goyal')).getByRole('button', { name: 'Enable' }));
    await waitFor(() => expect(row('Aryan Goyal')).toHaveTextContent('Active'));
  });

  it('sets a temporary password for someone else', async () => {
    const { user } = renderApp('/app/admin/users');
    await screen.findByRole('list', { name: 'Accounts' });
    await user.click(
      within(row('Aryan Goyal')).getByRole('button', {
        name: 'Set a temporary password for Aryan Goyal',
      }),
    );
    await user.type(screen.getByLabelText('Temporary password'), TEMPORARY);
    await user.click(screen.getByRole('button', { name: 'Set temporary password' }));

    expect(await screen.findByText(/^Aryan Goyal has a temporary password/)).toBeVisible();
    expect(mockApiState().users.find((u) => u.email === ARYAN_EMAIL)?.mustChangePassword).toBe(
      true,
    );
    expect(screen.queryByLabelText('Temporary password')).toBeNull();
  });
});

function addEvents(count: number, overrides: Partial<AuditEvent> = {}) {
  for (let i = 0; i < count; i += 1) {
    mockApiState().audit.push({
      id: `event-${mockApiState().audit.length}`,
      occurredAt: new Date(Date.UTC(2026, 9, 1, 9, 0, mockApiState().audit.length)).toISOString(),
      actorId: 'user-admin',
      actorName: 'Test Administrator',
      actorRole: 'Administrator',
      action: 'case.updated',
      outcome: 'success',
      targetType: 'case',
      targetId: 'case-1005',
      caseId: 'case-1005',
      caseNumber: 'LF-2026-0005',
      details: { fields: ['priority'] },
      ...overrides,
    });
  }
}

describe('the audit log', () => {
  it('shows entries newest first, with the case and the details', async () => {
    addEvents(1);
    addEvents(1, { action: 'auth.sign_in', caseId: null, caseNumber: null, details: {} });
    renderApp('/app/admin/audit');

    const rows = await screen.findAllByRole('row');
    expect(rows).toHaveLength(3);
    expect(rows[1]).toHaveTextContent('auth.sign_in');
    expect(within(rows[2]).getByRole('link', { name: 'LF-2026-0005' })).toHaveAttribute(
      'href',
      '/app/cases/case-1005',
    );
    expect(rows[2]).toHaveTextContent('fields: priority');
    expect(screen.getByText(/This is not tamper-proof/)).toBeVisible();
  });

  it('filters by outcome and loads older entries on request', async () => {
    addEvents(60);
    addEvents(2, { outcome: 'denied', actorName: 'Rajat Deshpande', action: 'case.view' });
    const { user } = renderApp('/app/admin/audit');

    expect(await screen.findAllByRole('row')).toHaveLength(51); // header + first 50
    await user.click(screen.getByRole('button', { name: 'Load older entries' }));
    await waitFor(() => expect(screen.getAllByRole('row')).toHaveLength(63));
    expect(screen.queryByRole('button', { name: 'Load older entries' })).toBeNull();

    await user.selectOptions(screen.getByLabelText('Outcome'), 'denied');
    await waitFor(() => expect(screen.getAllByRole('row')).toHaveLength(3));
    expect(screen.getAllByRole('cell', { name: 'Refused' })).toHaveLength(2);
  });

  it('is not shown to other roles', async () => {
    renderApp('/app/admin/audit', { as: ARYAN_EMAIL });
    expect(await screen.findByRole('status')).toHaveTextContent(
      'The audit log is for administrators.',
    );
  });
});
