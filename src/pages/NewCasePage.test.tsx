import { screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../test/renderApp';
import { mockCases, mockClients } from '../data/mockData';
import { todayIsoDate } from '../lib/format';

const futureDate = todayIsoDate(new Date(Date.now() + 30 * 24 * 60 * 60 * 1000));

describe('New case form', () => {
  it('rejects an empty submission, explains why, and stays on the form', async () => {
    const { url, user } = renderApp('/app/cases/new');

    await user.click(await screen.findByRole('button', { name: 'Create Case' }));

    expect(screen.getByRole('alert')).toHaveTextContent('3 fields need attention');
    const title = screen.getByLabelText(/Case Title/);
    expect(title).toHaveAttribute('aria-invalid', 'true');
    expect(title).toHaveAccessibleDescription(/at least 4 characters/);
    expect(screen.getByLabelText(/Client/)).toHaveAccessibleDescription(/Select a client/);
    expect(screen.getByLabelText(/Summary/)).toHaveAccessibleDescription(/at least 10/);
    // Focus moves to the first problem.
    expect(title).toHaveFocus();
    expect(url()).toBe('/app/cases/new');
  });

  it('rejects a next hearing date in the past', async () => {
    const { url, user } = renderApp('/app/cases/new');

    await user.type(await screen.findByLabelText(/Case Title/), 'Test Matter v. Other Party');
    await user.selectOptions(screen.getByLabelText(/Client/), mockClients[0].id);
    await user.type(screen.getByLabelText(/Summary/), 'A summary long enough to pass.');
    await user.type(screen.getByLabelText('Next Hearing Date'), '2000-01-01');
    await user.click(screen.getByRole('button', { name: 'Create Case' }));

    expect(screen.getByLabelText('Next Hearing Date')).toHaveAccessibleDescription(
      /cannot be in the past/,
    );
    expect(url()).toBe('/app/cases/new');
  });

  it('creates the case, opens its Documents tab, and lists it first', async () => {
    const { url, user } = renderApp('/app/cases/new');

    await user.type(await screen.findByLabelText(/Case Title/), 'Test Matter v. Other Party');
    await user.selectOptions(screen.getByLabelText(/Client/), mockClients[2].id);
    await user.type(screen.getByLabelText(/Summary/), 'A summary long enough to pass.');
    await user.type(screen.getByLabelText('Next Hearing Date'), futureDate);
    await user.click(screen.getByRole('button', { name: 'Create Case' }));

    await waitFor(() => expect(url()).toMatch(/^\/app\/cases\/case-[\w-]+\?tab=documents$/));
    expect(
      screen.getByRole('heading', { level: 1, name: 'Test Matter v. Other Party' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Documents/ })).toHaveAttribute('aria-selected', 'true');

    await user.click(screen.getByRole('link', { name: /All Cases/ }));
    const rows = await screen.findAllByRole('row');
    // Header row, then the new case first, then the sample cases.
    expect(rows).toHaveLength(mockCases.length + 2);
    expect(within(rows[1]).getByText('Test Matter v. Other Party')).toBeInTheDocument();
    expect(within(rows[1]).getByText(mockClients[2].name)).toBeInTheDocument();
  });
});
