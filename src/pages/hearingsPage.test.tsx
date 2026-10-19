import { screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { renderApp } from '../test/renderApp';
import { ARYAN_EMAIL, mockApiState, server } from '../test/mockApi';
import { formatDate, todayIsoDate } from '../lib/format';

// The firm-wide Hearings page. The server scopes and filters the schedule
// (server/tests/test_hearing_schedule.py); these tests check the page.

const SATTVIK = 'case-1005'; // led by Aryan Goyal

function inDays(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return todayIsoDate(d);
}

function addHearing(
  caseId: string,
  days: number,
  purpose: string,
  status: 'Scheduled' | 'Cancelled' = 'Scheduled',
) {
  const c = mockApiState().cases.find((k) => k.id === caseId);
  if (!c) throw new Error(`no case ${caseId}`);
  c.hearings.push({
    id: `${caseId}-${purpose}`,
    date: inDays(days),
    time: '10:00',
    court: 'Court Room 9',
    purpose,
    status,
    cancellationReason: status === 'Cancelled' ? 'Bench not sitting.' : null,
    isSample: false,
  });
}

const otherCase = () => mockApiState().cases.find((c) => c.id !== SATTVIK)?.id ?? '';

beforeEach(() => {
  addHearing(SATTVIK, 3, 'Sattvik mention');
  addHearing(otherCase(), 5, 'Other mention');
  addHearing(SATTVIK, 6, 'Sattvik adjourned', 'Cancelled');
  addHearing(SATTVIK, -10, 'Sattvik earlier');
});
afterEach(() => server.events.removeAllListeners());

describe('the Hearings page', () => {
  it('lists the coming hearings by day, with the case and its lead', async () => {
    renderApp('/app/hearings');
    const day = await screen.findByRole('list', { name: `Hearings on ${formatDate(inDays(3))}` });
    const item = within(day).getByText('Sattvik mention').closest('li') as HTMLElement;
    expect(within(item).getByRole('link')).toHaveAttribute('href', `/app/cases/${SATTVIK}`);
    expect(item).toHaveTextContent('Court Room 9 · Aryan Goyal');
    expect(screen.getByText('Other mention')).toBeVisible();
    expect(screen.queryByText('Sattvik adjourned')).toBeNull(); // cancelled
    expect(screen.queryByText('Sattvik earlier')).toBeNull(); // past
  });

  it('shows an Advocate only the hearings of their cases', async () => {
    renderApp('/app/hearings', { as: ARYAN_EMAIL });
    expect(await screen.findByText('Sattvik mention')).toBeVisible();
    expect(screen.queryByText('Other mention')).toBeNull();
  });

  it('shows cancelled hearings, marked, when asked', async () => {
    const { user } = renderApp('/app/hearings');
    await screen.findByText('Sattvik mention');
    await user.click(screen.getByLabelText('Show cancelled'));
    const item = (await screen.findByText('Sattvik adjourned')).closest('li');
    expect(item).toHaveTextContent('Cancelled · Bench not sitting.');
  });

  it('looks back with the "Past 30 days" period', async () => {
    const { user } = renderApp('/app/hearings');
    await screen.findByText('Sattvik mention');
    await user.click(screen.getByRole('button', { name: 'Past 30 days' }));
    expect(await screen.findByText('Sattvik earlier')).toBeVisible();
    expect(screen.queryByText('Sattvik mention')).toBeNull();
    expect(screen.getByRole('button', { name: 'Past 30 days' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('says when the end date is before the start, and asks the server nothing', async () => {
    const requested: string[] = [];
    server.events.on('request:start', ({ request }) => {
      requested.push(new URL(request.url).search);
    });
    const { user } = renderApp('/app/hearings');
    await screen.findByText('Sattvik mention');
    requested.length = 0;
    const to = screen.getByLabelText('To');
    await user.clear(to);
    await user.type(to, inDays(-5));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The end date must be on or after the start date.',
    );
    expect(to).toHaveAccessibleDescription('The end date must be on or after the start date.');
    await waitFor(() => expect(screen.queryByText('Sattvik mention')).toBeNull());
    expect(requested.filter((q) => q.includes(`to=${inDays(-5)}`))).toEqual([]);
  });
});
