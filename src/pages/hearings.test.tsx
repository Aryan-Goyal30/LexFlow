import { screen, waitFor, within } from '@testing-library/react';
import { http } from 'msw';
import { afterEach, describe, expect, it } from 'vitest';
import { renderApp } from '../test/renderApp';
import {
  MOCK_PARALEGAL_EMAIL,
  mockAddMember,
  mockApiState,
  problem,
  server,
} from '../test/mockApi';
import { formatDate, todayIsoDate } from '../lib/format';

// Scheduling, changing and cancelling hearings from the case overview. The
// server enforces the rules (server/tests/test_hearings.py).

const SATTVIK = 'case-1005';

function daysFromToday(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return todayIsoDate(d);
}

function captureBodies(method: string): unknown[] {
  const bodies: unknown[] = [];
  server.events.on('request:start', ({ request }) => {
    if (request.method === method && new URL(request.url).pathname.includes('hearing')) {
      void request
        .clone()
        .json()
        .then((body) => bodies.push(body));
    }
  });
  return bodies;
}

afterEach(() => server.events.removeAllListeners());

const hearingsList = () => screen.getByRole('list', { name: 'Hearings' });

describe('hearings', () => {
  it('lets a paralegal on the team schedule one, which becomes the next hearing', async () => {
    mockAddMember(SATTVIK, MOCK_PARALEGAL_EMAIL, 'paralegal');
    const date = daysFromToday(20);
    const { user } = renderApp(`/app/cases/${SATTVIK}`, { as: MOCK_PARALEGAL_EMAIL });

    await user.click(await screen.findByRole('button', { name: 'Schedule hearing' }));
    const form = screen.getByRole('form', { name: 'Schedule a hearing' });
    await user.type(within(form).getByLabelText(/^Date/), date);
    await user.type(within(form).getByLabelText('Time'), '10:30');
    const court = within(form).getByLabelText(/Court \/ Forum/);
    await user.clear(court);
    await user.type(court, 'Court Room 12');
    await user.type(within(form).getByLabelText(/Purpose/), 'Arguments on interim relief');
    await user.click(within(form).getByRole('button', { name: 'Schedule' }));

    expect(await screen.findByText(`Hearing scheduled for ${formatDate(date)}.`)).toBeVisible();
    const item = within(hearingsList()).getByText('Arguments on interim relief').closest('li');
    expect(item).toHaveTextContent(`${formatDate(date)} · 10:30 · Court Room 12`);
    expect(screen.getByText(new RegExp(`Next hearing ${formatDate(date)}`))).toBeVisible();
    expect(screen.getByText('Hearing scheduled')).toBeInTheDocument(); // timeline
  });

  it('checks the form before sending it and focuses the first problem', async () => {
    const bodies = captureBodies('POST');
    const { user } = renderApp(`/app/cases/${SATTVIK}`);
    await user.click(await screen.findByRole('button', { name: 'Schedule hearing' }));
    const form = screen.getByRole('form', { name: 'Schedule a hearing' });
    await user.type(within(form).getByLabelText(/^Date/), daysFromToday(-1));
    await user.click(within(form).getByRole('button', { name: 'Schedule' }));

    const date = within(form).getByLabelText(/^Date/);
    expect(date).toHaveAccessibleDescription('The hearing date cannot be in the past.');
    expect(date).toHaveFocus();
    expect(within(form).getByLabelText(/Purpose/)).toHaveAccessibleDescription(
      'Enter the purpose of the hearing.',
    );
    expect(bodies).toEqual([]);
  });

  it('shows the server reason beside the field', async () => {
    server.use(
      http.post('*/api/cases/:id/hearings', () =>
        problem(422, 'validation-error', 'Correct the highlighted fields and try again.', [
          { field: 'court', message: 'Keep this under 201 characters.' },
        ]),
      ),
    );
    const { user } = renderApp(`/app/cases/${SATTVIK}`);
    await user.click(await screen.findByRole('button', { name: 'Schedule hearing' }));
    const form = screen.getByRole('form', { name: 'Schedule a hearing' });
    await user.type(within(form).getByLabelText(/^Date/), daysFromToday(5));
    await user.type(within(form).getByLabelText(/Purpose/), 'Mention');
    await user.click(within(form).getByRole('button', { name: 'Schedule' }));

    await waitFor(() =>
      expect(within(form).getByLabelText(/Court \/ Forum/)).toHaveAccessibleDescription(
        'Keep this under 201 characters.',
      ),
    );
  });

  it('changes a hearing, sending only what changed', async () => {
    const bodies = captureBodies('PATCH');
    const { user } = renderApp(`/app/cases/${SATTVIK}`);
    const first = mockApiState().cases.find((c) => c.id === SATTVIK)?.hearings[0];
    if (!first) throw new Error('the sample case has a hearing');

    await user.click(
      await screen.findByRole('button', { name: `Change hearing: ${first.purpose}` }),
    );
    const form = screen.getByRole('form', { name: `Change hearing: ${first.purpose}` });
    const court = within(form).getByLabelText(/Court \/ Forum/);
    await user.clear(court);
    await user.type(court, 'Court Room 3');
    await user.click(within(form).getByRole('button', { name: 'Save' }));

    expect(await screen.findByText('Hearing updated.')).toBeVisible();
    expect(within(hearingsList()).getByText(/Court Room 3/)).toBeVisible();
    expect(bodies).toEqual([{ court: 'Court Room 3' }]);
  });

  it('cancels a hearing with a reason and keeps it listed', async () => {
    const bodies = captureBodies('POST');
    const { user } = renderApp(`/app/cases/${SATTVIK}`);
    const first = mockApiState().cases.find((c) => c.id === SATTVIK)?.hearings[0];
    if (!first) throw new Error('the sample case has a hearing');

    await user.click(
      await screen.findByRole('button', { name: `Cancel hearing: ${first.purpose}` }),
    );
    const reason = screen.getByLabelText('Reason (optional)');
    expect(reason).toHaveFocus();
    await user.type(reason, 'Bench not sitting.');
    await user.click(screen.getByRole('button', { name: 'Cancel hearing' }));

    expect(
      await screen.findByText(`Hearing on ${formatDate(first.date)} cancelled.`),
    ).toBeVisible();
    const item = within(hearingsList()).getByText(first.purpose).closest('li') as HTMLElement;
    expect(item).toHaveTextContent('Cancelled · Bench not sitting.');
    expect(within(item).queryByRole('button', { name: /Change hearing/ })).toBeNull();
    expect(within(item).queryByRole('button', { name: /Cancel hearing/ })).toBeNull();
    expect(bodies).toEqual([{ reason: 'Bench not sitting.' }]);
  });

  it('offers no changes on an archived case', async () => {
    const stored = mockApiState().cases.find((c) => c.id === SATTVIK);
    if (stored) stored.archivedAt = '2026-01-15T10:00:00Z';
    renderApp(`/app/cases/${SATTVIK}`);
    await screen.findByRole('list', { name: 'Hearings' });
    expect(screen.queryByRole('button', { name: 'Schedule hearing' })).toBeNull();
    expect(screen.queryByRole('button', { name: /^Change hearing/ })).toBeNull();
    expect(screen.queryByRole('button', { name: /^Cancel hearing/ })).toBeNull();
  });
});
