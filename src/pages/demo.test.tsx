import { screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../test/renderApp';
import { ARYAN_EMAIL, mockApiState, mockDemo } from '../test/mockApi';
import { todayIsoDate } from '../lib/format';

// The isolated demo environment (Milestone 1) against the fake API: the
// banner, and the fictional client and case options, appear only when the
// server reports the verified demo database. The server's own checks are in
// server/tests/test_demo_mode.py.

const futureDate = todayIsoDate(new Date(Date.now() + 30 * 24 * 60 * 60 * 1000));

async function addClient(
  user: ReturnType<typeof renderApp>['user'],
  name: string,
  fictional: boolean,
) {
  if (fictional)
    await user.click(await screen.findByRole('checkbox', { name: /Fictional demo client/ }));
  await user.type(await screen.findByLabelText(/Name/), name);
  await user.type(screen.getByLabelText(/E-mail/), 'legal@velorindra-foods.example');
  await user.type(screen.getByLabelText(/Phone/), '+91 00000 14014');
  await user.click(screen.getByRole('button', { name: 'Add Client' }));
}

describe('The demo environment', () => {
  it('shows nothing about demos while demo mode is off', async () => {
    renderApp('/app/cases/new', { as: ARYAN_EMAIL });
    expect(await screen.findByLabelText(/Case Title/)).toBeVisible();
    expect(screen.queryByRole('complementary', { name: 'Demo environment' })).toBeNull();
    expect(screen.queryByRole('checkbox', { name: /Fictional demo case/ })).toBeNull();
  });

  it('warns, and offers nothing fictional, when the demo database is not verified', async () => {
    mockDemo(false);
    renderApp('/app/clients/new', { as: ARYAN_EMAIL });
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not be verified/);
    expect(await screen.findByLabelText(/Name/)).toBeVisible();
    expect(screen.queryByRole('checkbox', { name: /Fictional demo client/ })).toBeNull();
  });

  it('creates a fictional client and a fictional case in the verified demo database', async () => {
    mockDemo(true);
    const { user, url } = renderApp('/app/clients/new', { as: ARYAN_EMAIL });
    expect(
      await screen.findByRole('complementary', { name: 'Demo environment' }),
    ).toHaveTextContent(/Every client, case, document and judgment here is fictional/);
    await addClient(user, 'Velorindra Foods LLP (FICTIONAL)', true);
    await waitFor(() => expect(url()).toMatch(/^\/app\/cases\/new\?client=/));
    const client = mockApiState().clients.find((c) => c.name.startsWith('Velorindra'));
    expect(client?.isSample).toBe(true);

    await user.click(await screen.findByRole('checkbox', { name: /Fictional demo case/ }));
    await user.type(screen.getByLabelText(/Case Title/), 'Velorindra v. Tamsinwick (FICTIONAL)');
    await user.type(screen.getByLabelText(/Summary/), 'FICTIONAL demo matter: trade mark KESORA.');
    await user.type(screen.getByLabelText('Next Hearing Date'), futureDate);
    await user.click(screen.getByRole('button', { name: 'Create Case' }));
    await waitFor(() => expect(url()).toMatch(/^\/app\/cases\/case-new-\d+/));
    const created = mockApiState().cases.find((c) => c.title.startsWith('Velorindra'));
    expect(created?.isSample).toBe(true);
  });

  it('refuses a fictional case for a client that is not fictional', async () => {
    mockDemo(true);
    const { user, url } = renderApp('/app/clients/new', { as: ARYAN_EMAIL });
    await addClient(user, 'Ordinary Client LLP', false);
    await waitFor(() => expect(url()).toMatch(/^\/app\/cases\/new\?client=/));
    await user.click(await screen.findByRole('checkbox', { name: /Fictional demo case/ }));
    await user.type(screen.getByLabelText(/Case Title/), 'Ordinary v. Other');
    await user.type(screen.getByLabelText(/Summary/), 'A summary long enough to pass.');
    await user.click(screen.getByRole('button', { name: 'Create Case' }));
    expect(await screen.findByLabelText(/Client/)).toHaveAccessibleDescription(
      /needs a fictional \(sample\) client/,
    );
    expect(mockApiState().cases.some((c) => c.title === 'Ordinary v. Other')).toBe(false);
  });
});
