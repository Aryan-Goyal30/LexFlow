import { screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../../test/renderApp';
import {
  ARYAN_EMAIL,
  MOCK_PARALEGAL_EMAIL,
  mockAddMember,
  mockAddUser,
  mockApiState,
} from '../../test/mockApi';
import { todayIsoDate } from '../../lib/format';

// The client portal. The server proves the isolation (server/tests/test_portal.py);
// these tests check what the screens show and offer.

const SATTVIK = 'case-1005';
const CLIENT_EMAIL = 'contact@client.example';

function sattvik() {
  const c = mockApiState().cases.find((k) => k.id === SATTVIK);
  if (!c) throw new Error('no Sattvik case');
  return c;
}

function addClientAccount() {
  mockAddUser({
    email: CLIENT_EMAIL,
    role: 'Client',
    name: 'Sattvik Contact',
    clientId: sattvik().clientId,
  });
}

function inDays(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return todayIsoDate(d);
}

describe('the client portal', () => {
  it("lists only the client's own cases", async () => {
    addClientAccount();
    renderApp('/portal', { as: CLIENT_EMAIL });

    const list = await screen.findByRole('list', { name: 'Your cases' });
    const titles = within(list)
      .getAllByRole('link')
      .map((a) => a.textContent);
    const own = mockApiState()
      .cases.filter((c) => c.clientId === sattvik().clientId)
      .map((c) => c.title);
    expect(titles.sort()).toEqual(own.sort());
  });

  it('shows coming hearings and only the documents shared with the client', async () => {
    addClientAccount();
    const c = sattvik();
    const [shared, unshared] = c.documents;
    Object.assign(shared, { hasFile: true, sharedWithClientAt: '2026-10-01T10:00:00Z' });
    Object.assign(unshared, { hasFile: true, sharedWithClientAt: null });
    c.hearings.push(
      {
        id: 'coming',
        date: inDays(4),
        time: '11:00',
        court: 'Court Room 2',
        purpose: 'Final arguments',
        status: 'Scheduled',
        cancellationReason: null,
        isSample: false,
      },
      {
        id: 'called-off',
        date: inDays(5),
        time: null,
        court: 'Court Room 2',
        purpose: 'Called-off mention',
        status: 'Cancelled',
        cancellationReason: 'Internal note',
        isSample: false,
      },
    );
    renderApp(`/portal/cases/${SATTVIK}`, { as: CLIENT_EMAIL });

    const documents = await screen.findByRole('list', { name: 'Shared documents' });
    expect(within(documents).getByText(shared.name)).toBeVisible();
    expect(
      within(documents).getByRole('link', { name: `Download ${shared.name}` }),
    ).toHaveAttribute('href', `/api/portal/documents/${shared.id}/download`);
    expect(screen.queryByText(unshared.name)).toBeNull();
    const hearings = screen.getByRole('list', { name: 'Coming hearings' });
    expect(within(hearings).getByText('Final arguments')).toBeVisible();
    expect(screen.queryByText('Called-off mention')).toBeNull();
    expect(screen.queryByText('Internal note')).toBeNull();
    // No internal details reach the client.
    expect(screen.queryByText(c.description)).toBeNull();
  });

  it("reports another client's case as not found", async () => {
    addClientAccount();
    const other = mockApiState().cases.find((k) => k.clientId !== sattvik().clientId);
    renderApp(`/portal/cases/${other?.id}`, { as: CLIENT_EMAIL });
    expect(await screen.findByText('Case not found')).toBeVisible();
  });

  it('keeps a signed-in client out of the staff app', async () => {
    addClientAccount();
    const { url } = renderApp('/app/cases', { as: CLIENT_EMAIL });
    await waitFor(() => expect(url()).toBe('/portal'));
    expect(await screen.findByRole('heading', { name: 'Your Cases' })).toBeVisible();
  });

  it('sends staff back to the app', async () => {
    const { url } = renderApp('/portal');
    await waitFor(() => expect(url()).toBe('/app/cases'));
  });
});

describe('sharing documents with the client', () => {
  it('lets the lead share an uploaded document and stop sharing it', async () => {
    const { user } = renderApp(`/app/cases/${SATTVIK}?tab=documents`, { as: ARYAN_EMAIL });
    const picker = await screen.findByLabelText('Choose files to attach');
    await user.upload(
      picker,
      new File(['%PDF-1.4\n%%EOF\n'], 'Advice.pdf', { type: 'application/pdf' }),
    );
    await user.click(
      await screen.findByRole('button', { name: 'Share Advice.pdf with the client' }),
    );

    expect(
      await screen.findByText('Shared Advice.pdf with the client: it is now in their portal.'),
    ).toBeVisible();
    const row = screen.getByText('Advice.pdf').closest('li') as HTMLElement;
    await waitFor(() => expect(row).toHaveTextContent('Shared with client'));

    await user.click(
      within(row).getByRole('button', { name: 'Stop sharing Advice.pdf with the client' }),
    );
    expect(
      await screen.findByText("Stopped sharing Advice.pdf: it has left the client's portal."),
    ).toBeVisible();
  });

  it('offers no sharing to a paralegal, even for a file they uploaded', async () => {
    mockAddMember(SATTVIK, MOCK_PARALEGAL_EMAIL, 'paralegal');
    const { user } = renderApp(`/app/cases/${SATTVIK}?tab=documents`, {
      as: MOCK_PARALEGAL_EMAIL,
    });
    const picker = await screen.findByLabelText('Choose files to attach');
    await user.upload(
      picker,
      new File(['%PDF-1.4\n%%EOF\n'], 'Note.pdf', { type: 'application/pdf' }),
    );
    expect(await screen.findByRole('link', { name: 'Open Note.pdf' })).toBeVisible();
    expect(screen.queryByRole('button', { name: /with the client$/ })).toBeNull();
  });
});
