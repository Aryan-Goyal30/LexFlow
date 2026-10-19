import { screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { renderApp } from '../test/renderApp';
import {
  ARYAN_EMAIL,
  MOCK_PARALEGAL_EMAIL,
  mockAddMember,
  mockAddUser,
  mockApiState,
  server,
} from '../test/mockApi';

// Editing a case, changing its status, archiving it and building its team.
// The server enforces every rule (server/tests/test_case_workflows.py); these
// tests check that the screens offer the right controls and send only changes.

const SATTVIK = 'case-1005'; // led by Aryan Goyal
const ASSOCIATE = 'associate@lexflow.test';

/** The JSON bodies of PATCH requests sent while a test runs. */
function capturePatches(): unknown[] {
  const bodies: unknown[] = [];
  const listener = ({ request }: { request: Request }) => {
    if (request.method === 'PATCH') {
      void request
        .clone()
        .json()
        .then((body) => bodies.push(body));
    }
  };
  server.events.on('request:start', listener);
  return bodies;
}

afterEach(() => server.events.removeAllListeners());

describe('editing a case', () => {
  it('lets the lead change the status and title, sending only what changed', async () => {
    const patches = capturePatches();
    const { user, url } = renderApp(`/app/cases/${SATTVIK}`, { as: ARYAN_EMAIL });

    await user.click(await screen.findByRole('link', { name: 'Edit case' }));
    const title = await screen.findByLabelText(/Case Title/);
    await user.clear(title);
    await user.type(title, 'Sattvik Foods v. Annapurna Snacks (amended)');
    await user.selectOptions(screen.getByLabelText('Status'), 'Closed');
    await user.click(screen.getByRole('button', { name: 'Save Changes' }));

    expect(
      await screen.findByRole('heading', {
        level: 1,
        name: 'Sattvik Foods v. Annapurna Snacks (amended)',
      }),
    ).toBeVisible();
    expect(url()).toBe(`/app/cases/${SATTVIK}`);
    expect(patches).toEqual([
      { title: 'Sattvik Foods v. Annapurna Snacks (amended)', status: 'Closed' },
    ]);
    // The timeline says what changed, who changed it and when.
    const entry = screen.getByText(/Title updated\. Status changed from .* to Closed\./);
    expect(entry.closest('li')).toHaveTextContent(/at .* · Aryan Goyal/);
  });

  it('says so when nothing has changed, and sends nothing', async () => {
    const patches = capturePatches();
    const { user } = renderApp(`/app/cases/${SATTVIK}/edit`, { as: ARYAN_EMAIL });

    await user.click(await screen.findByRole('button', { name: 'Save Changes' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Nothing has changed yet.');
    expect(patches).toEqual([]);
  });

  it('clears an optional field when it is emptied', async () => {
    const patches = capturePatches();
    const { user } = renderApp(`/app/cases/${SATTVIK}/edit`, { as: ARYAN_EMAIL });

    await user.clear(await screen.findByLabelText('Opposing Party'));
    await user.click(screen.getByRole('button', { name: 'Save Changes' }));
    await screen.findByRole('heading', { level: 1, name: /Sattvik/ });
    expect(patches).toEqual([{ opposingParty: null }]);
  });

  it('checks the title before sending and focuses it', async () => {
    const patches = capturePatches();
    const { user } = renderApp(`/app/cases/${SATTVIK}/edit`, { as: ARYAN_EMAIL });

    const title = await screen.findByLabelText(/Case Title/);
    await user.clear(title);
    await user.type(title, 'Abc');
    await user.click(screen.getByRole('button', { name: 'Save Changes' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('One field needs attention');
    expect(title).toHaveAccessibleDescription(
      'Enter a descriptive case title (at least 4 characters).',
    );
    expect(title).toHaveFocus();
    expect(patches).toEqual([]);
  });

  it('offers a Paralegal only the court and the opposing party', async () => {
    mockAddMember(SATTVIK, MOCK_PARALEGAL_EMAIL, 'paralegal');
    const patches = capturePatches();
    const { user } = renderApp(`/app/cases/${SATTVIK}/edit`, { as: MOCK_PARALEGAL_EMAIL });

    const court = await screen.findByLabelText('Court / Forum');
    expect(screen.getByLabelText('Opposing Party')).toBeInTheDocument();
    for (const hidden of [/Case Title/, 'Status', 'Priority', 'Lead Advocate', 'Client']) {
      expect(screen.queryByLabelText(hidden)).toBeNull();
    }
    expect(screen.getByRole('note')).toHaveTextContent(
      'you can update the court and the opposing party',
    );

    await user.clear(court);
    await user.type(court, 'High Court of Bombay');
    await user.click(screen.getByRole('button', { name: 'Save Changes' }));
    await screen.findByRole('heading', { level: 1, name: /Sattvik/ });
    expect(patches).toEqual([{ courtName: 'High Court of Bombay' }]);
  });

  it('lets only an Administrator change the lead and the client', async () => {
    renderApp(`/app/cases/${SATTVIK}/edit`, { as: ARYAN_EMAIL });
    await screen.findByLabelText(/Case Title/);
    expect(screen.queryByLabelText('Lead Advocate')).toBeNull();
    expect(screen.queryByLabelText('Client')).toBeNull();
  });

  it('shows the server reason beside the field it refused', async () => {
    const { http } = await import('msw');
    const { problem } = await import('../test/mockApi');
    server.use(
      http.patch('*/api/cases/:id', () =>
        problem(403, 'field-not-permitted', 'You cannot change this field on this case.', [
          { field: 'status', message: 'You cannot change this field on this case.' },
        ]),
      ),
    );
    const { user } = renderApp(`/app/cases/${SATTVIK}/edit`, { as: ARYAN_EMAIL });
    const status = await screen.findByLabelText('Status');
    await user.selectOptions(status, 'On Hold');
    await user.click(screen.getByRole('button', { name: 'Save Changes' }));

    await waitFor(() =>
      expect(status).toHaveAccessibleDescription('You cannot change this field on this case.'),
    );
    expect(status).toHaveDisplayValue('On Hold'); // the input is kept
  });
});

describe('archiving a case', () => {
  it('asks the Administrator to confirm, then makes the case read-only', async () => {
    const { user } = renderApp(`/app/cases/${SATTVIK}?tab=documents`);
    await user.click(await screen.findByRole('button', { name: 'Archive case' }));

    // Cancelling changes nothing.
    const prompt = screen.getByRole('group', { name: /Archive this case\?/ });
    await user.click(within(prompt).getByRole('button', { name: 'Cancel' }));
    expect(mockApiState().cases.find((c) => c.id === SATTVIK)?.archivedAt).toBeNull();

    await user.click(screen.getByRole('button', { name: 'Archive case' }));
    expect(screen.getByRole('button', { name: 'Archive' })).toHaveFocus();
    await user.click(screen.getByRole('button', { name: 'Archive' }));

    expect(await screen.findByText(/^Archived on /)).toBeVisible();
    expect(screen.getByText(/This case is read-only/)).toHaveTextContent('until you restore it');
    expect(screen.queryByRole('link', { name: 'Edit case' })).toBeNull();
    // The drop zone stays mounted (an upload may be finishing) but is hidden.
    expect(screen.getByLabelText('Choose files to attach')).not.toBeVisible();
    expect(screen.getByText("You can open this case's documents.")).toBeVisible();
    expect(screen.queryByRole('button', { name: /^Remove / })).toBeNull();
    expect(screen.getByText('Cease and Desist Notice.pdf')).toBeInTheDocument(); // still there

    // Hidden from the case list unless asked for.
    await user.click(screen.getByRole('link', { name: /All Cases/ }));
    await screen.findAllByRole('row');
    expect(screen.queryByRole('link', { name: /Sattvik/ })).toBeNull();
    await user.click(screen.getByLabelText('Show archived'));
    const row = (await screen.findByRole('link', { name: /Sattvik/ })).closest('tr');
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getByText('Archived')).toBeVisible();

    // Restoring puts it back.
    await user.click(within(row as HTMLElement).getByRole('link', { name: /Sattvik/ }));
    await user.click(await screen.findByRole('button', { name: 'Restore case' }));
    await waitFor(() => expect(screen.queryByText(/^Archived on /)).toBeNull());
    expect(screen.getByRole('link', { name: 'Edit case' })).toBeVisible();
  });

  it('is not offered to the lead advocate', async () => {
    renderApp(`/app/cases/${SATTVIK}`, { as: ARYAN_EMAIL });
    await screen.findByRole('link', { name: 'Edit case' });
    expect(screen.queryByRole('button', { name: 'Archive case' })).toBeNull();
  });

  it('tells the lead an archived case cannot be edited', async () => {
    const stored = mockApiState().cases.find((c) => c.id === SATTVIK);
    if (stored) stored.archivedAt = '2026-01-15T10:00:00Z';
    renderApp(`/app/cases/${SATTVIK}/edit`, { as: ARYAN_EMAIL });
    expect(
      await screen.findByText(
        'This case is archived, so it cannot be changed. An administrator can restore it.',
      ),
    ).toBeVisible();
    expect(screen.queryByRole('form')).toBeNull();
  });
});

describe('the case team', () => {
  beforeEach(() => {
    mockAddUser({ email: ASSOCIATE, role: 'Advocate', name: 'Associate Advocate' });
    mockAddMember(SATTVIK, ASSOCIATE, 'associate');
  });

  it('lets the lead add a paralegal and take them off again', async () => {
    const { user } = renderApp(`/app/cases/${SATTVIK}`, { as: ARYAN_EMAIL });
    const team = await screen.findByRole('list', { name: 'Case team' });
    expect(within(team).getByText('Aryan Goyal')).toBeVisible();
    expect(within(team).getByText('Associate Advocate')).toBeVisible();

    const choose = await screen.findByLabelText('Add to the team');
    // The lead and current members are not offered.
    const offered = within(choose)
      .getAllByRole('option')
      .map((o) => o.textContent);
    expect(offered).not.toContain('Aryan Goyal (advocate)');
    expect(offered).not.toContain('Associate Advocate (advocate)');

    await user.selectOptions(choose, 'Test Paralegal (paralegal)');
    await user.click(screen.getByRole('button', { name: 'Add' }));
    expect(await within(team).findByText('Test Paralegal')).toBeVisible();
    expect(
      screen.getByText('Test Paralegal joined the case team as a paralegal.'),
    ).toBeInTheDocument();

    await user.click(
      screen.getByRole('button', { name: 'Remove Test Paralegal from the case team' }),
    );
    await waitFor(() => expect(within(team).queryByText('Test Paralegal')).toBeNull());
    expect(screen.getByText('Test Paralegal left the case team.')).toBeInTheDocument();
  });

  it('shows an associate the team but no way to change it', async () => {
    renderApp(`/app/cases/${SATTVIK}`, { as: ASSOCIATE });
    const team = await screen.findByRole('list', { name: 'Case team' });
    expect(within(team).getByText('Associate Advocate')).toBeVisible();
    expect(screen.queryByLabelText('Add to the team')).toBeNull();
    expect(screen.queryByRole('button', { name: /^Remove .* from the case team$/ })).toBeNull();
    // An associate may still edit the details and status.
    expect(screen.getByRole('link', { name: 'Edit case' })).toBeVisible();
  });
});
