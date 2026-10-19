import { screen, waitFor, within } from '@testing-library/react';
import { delay, http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { renderApp } from './test/renderApp';
import {
  MOCK_ADMIN_EMAIL,
  MOCK_PASSWORD,
  mockAddUser,
  mockApiState,
  mockSignOut,
  server,
} from './test/mockApi';

type User = ReturnType<typeof renderApp>['user'];

async function signInWithForm(user: User, email: string, password = MOCK_PASSWORD) {
  await user.type(await screen.findByLabelText('Email address'), email);
  await user.type(screen.getByLabelText('Password'), password);
  await user.click(screen.getByRole('button', { name: 'Sign in' }));
}

describe('route guard and sign-in', () => {
  it('sends a signed-out visitor to sign-in, then to the case list', async () => {
    const { url, user } = renderApp('/app/cases', { signedIn: false });

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
    expect(url()).toBe('/');
    // Nothing is pre-filled: there are no demo credentials.
    expect(screen.getByLabelText('Email address')).toHaveValue('');
    expect(screen.getByLabelText('Password')).toHaveValue('');

    await signInWithForm(user, 'aryan.goyal@lexflow.test');

    await waitFor(() => expect(url()).toBe('/app/cases'));
    expect(await screen.findByRole('heading', { name: 'Cases' })).toBeInTheDocument();
    expect(screen.getByText('Aryan Goyal')).toBeInTheDocument();
  });

  it('returns to the originally requested page after sign-in', async () => {
    const { url, user } = renderApp('/app/cases/case-1005?tab=research', { signedIn: false });

    await signInWithForm(user, 'aryan.goyal@lexflow.test');

    await waitFor(() => expect(url()).toBe('/app/cases/case-1005?tab=research'));
    // The workspace loads the case from the API before its tabs appear.
    expect(await screen.findByRole('tab', { name: /Research/ })).toHaveAttribute(
      'aria-selected',
      'true',
    );
  });

  it('requires an email and password before signing in', async () => {
    const { url, user } = renderApp('/', { signedIn: false });

    await user.click(await screen.findByRole('button', { name: 'Sign in' }));

    expect(screen.getByRole('alert')).toHaveTextContent('Enter your email and password');
    expect(url()).toBe('/');
  });

  it('gives the same answer for a wrong password and an unknown account', async () => {
    const { url, user } = renderApp('/', { signedIn: false });

    await signInWithForm(user, 'aryan.goyal@lexflow.test', 'not the password');
    expect(await screen.findByRole('alert')).toHaveTextContent('Email or password is incorrect.');
    expect(screen.getByLabelText('Password')).toHaveValue(''); // cleared for the next attempt

    await user.clear(screen.getByLabelText('Email address'));
    await signInWithForm(user, 'nobody@lexflow.test');
    expect(await screen.findByRole('alert')).toHaveTextContent('Email or password is incorrect.');
    expect(url()).toBe('/');
  });

  it('sends a Client to the portal, never into the staff app', async () => {
    mockAddUser({
      email: 'contact@client.example',
      role: 'Client',
      name: 'A Client',
      clientId: 'c-005',
    });
    // Even when the link they followed pointed into the staff app.
    const { url, user } = renderApp('/app/cases', { signedIn: false });
    await waitFor(() => expect(url()).toBe('/'));

    await signInWithForm(user, 'contact@client.example');

    await waitFor(() => expect(url()).toBe('/portal'));
    expect(await screen.findByRole('heading', { name: 'Your Cases' })).toBeVisible();
  });

  it('explains how accounts are created, and does not pretend sign-in is simulated', async () => {
    renderApp('/', { signedIn: false });
    expect(await screen.findByText(/created by an administrator/)).toBeInTheDocument();
    expect(screen.queryByText(/simulat/i)).not.toBeInTheDocument();
  });

  it('skips the sign-in page for a signed-in user', async () => {
    const { url } = renderApp('/');
    await waitFor(() => expect(url()).toBe('/app/cases'));
  });

  it('opens the case list at /app', async () => {
    const { url } = renderApp('/app');
    await waitFor(() => expect(url()).toBe('/app/cases'));
  });

  it('shows a 404 page that links back to the cases', async () => {
    const { url, user } = renderApp('/no/such/page');

    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
    await user.click(screen.getByRole('link', { name: 'Go to cases' }));
    await waitFor(() => expect(url()).toBe('/app/cases'));
  });
});

describe('signing out and switching accounts', () => {
  it('signs out on the server, forgets cached data and protects the pages again', async () => {
    const { url, user, queryClient } = renderApp('/app/cases');
    expect(await screen.findAllByRole('row')).not.toHaveLength(0);

    await user.click(screen.getByRole('button', { name: 'Sign out' }));

    await waitFor(() => expect(url()).toBe('/'));
    expect(mockApiState().sessionUserId).toBeNull();
    // Only "who is signed in" (nobody) remains in the cache.
    const cached = queryClient.getQueryCache().findAll();
    expect(cached.map((q) => q.queryKey)).toEqual([['auth', 'me']]);
    expect(cached[0].state.data).toBeNull();
  });

  it("never shows the previous person's cases to the next person on the same browser", async () => {
    const { url, user } = renderApp('/app/cases');
    expect(
      await screen.findByRole('link', { name: /Sattvik Foods Pvt\. Ltd\. v\./ }),
    ).toBeVisible();

    await user.click(screen.getByRole('button', { name: 'Sign out' }));
    await waitFor(() => expect(url()).toBe('/'));
    // The next person sees a different set of cases, and the server is slow to
    // answer: a cached list from the previous person would show meanwhile.
    server.use(
      http.get('*/api/cases', async () => {
        await delay(300);
        return HttpResponse.json([]);
      }),
    );
    await signInWithForm(user, MOCK_ADMIN_EMAIL);

    await waitFor(() => expect(url()).toBe('/app/cases'));
    expect(screen.getByRole('status')).toHaveTextContent('Loading cases');
    expect(screen.queryByRole('link', { name: /Sattvik Foods/ })).toBeNull();
    expect(await screen.findByText('No cases yet')).toBeInTheDocument();
  });

  it('goes back to sign-in, and then to the same page, when the session ends', async () => {
    const { url, user } = renderApp('/app/cases');
    expect(await screen.findByRole('heading', { name: 'Cases' })).toBeInTheDocument();

    mockSignOut(); // expired or revoked on the server
    await user.click(screen.getByRole('link', { name: /Practice Overview/ }));

    await waitFor(() => expect(url()).toBe('/'));
    await signInWithForm(user, 'aryan.goyal@lexflow.test');
    await waitFor(() => expect(url()).toBe('/app/dashboard'));
  });

  it('removes the old simulated sign-in record from the browser', async () => {
    localStorage.setItem('lexflow.auth', JSON.stringify({ name: 'Old Mock User' }));
    renderApp('/', { signedIn: false });
    await screen.findByRole('heading', { name: 'Sign in' });
    expect(localStorage.getItem('lexflow.auth')).toBeNull();
  });
});

describe('temporary passwords', () => {
  it('sends the user to change it first, then on to the app', async () => {
    mockAddUser({ email: 'temp@lexflow.test', role: 'Advocate', mustChangePassword: true });
    const { url, user } = renderApp('/app/cases/case-1005', { as: 'temp@lexflow.test' });

    await waitFor(() => expect(url()).toBe('/app/account/password'));
    expect(screen.getByText(/temporary password/)).toBeInTheDocument();

    const form = screen.getByRole('form', { name: 'Change password' });
    await user.type(within(form).getByLabelText(/Current password/), MOCK_PASSWORD);
    await user.type(within(form).getByLabelText(/^New password/), 'my own passphrase now');
    await user.type(
      within(form).getByLabelText(/Repeat the new password/),
      'my own passphrase now',
    );
    await user.click(within(form).getByRole('button', { name: 'Change password' }));

    await waitFor(() => expect(url()).toBe('/app/cases'));
  });

  it('shows the server reason beside the field when the current password is wrong', async () => {
    const { user } = renderApp('/app/account/password');
    const form = await screen.findByRole('form', { name: 'Change password' });

    await user.type(within(form).getByLabelText(/Current password/), 'wrong password');
    await user.type(within(form).getByLabelText(/^New password/), 'my own passphrase now');
    await user.type(
      within(form).getByLabelText(/Repeat the new password/),
      'my own passphrase now',
    );
    await user.click(within(form).getByRole('button', { name: 'Change password' }));

    expect(await within(form).findByLabelText(/Current password/)).toHaveAccessibleDescription(
      'Your current password is incorrect.',
    );
  });

  it('checks that the two new passwords match before sending them', async () => {
    let sent = false;
    server.use(
      http.post('*/api/auth/password', () => {
        sent = true;
        return undefined;
      }),
    );
    const { user } = renderApp('/app/account/password');
    const form = await screen.findByRole('form', { name: 'Change password' });

    await user.type(within(form).getByLabelText(/Current password/), MOCK_PASSWORD);
    await user.type(within(form).getByLabelText(/^New password/), 'my own passphrase now');
    await user.type(
      within(form).getByLabelText(/Repeat the new password/),
      'something else entirely',
    );
    await user.click(within(form).getByRole('button', { name: 'Change password' }));

    expect(within(form).getByLabelText(/Repeat the new password/)).toHaveAccessibleDescription(
      'The two new passwords do not match.',
    );
    expect(sent).toBe(false);
  });
});

describe('checking the session', () => {
  it('asks the server who is signed in before showing a page', async () => {
    renderApp('/app/cases', { sessionKnown: false });
    expect(screen.getByRole('status')).toHaveTextContent('Checking your session');
    expect(await screen.findByRole('heading', { name: 'Cases' })).toBeInTheDocument();
  });

  it('offers a retry, not the sign-in page, when the server cannot be reached', async () => {
    server.use(http.get('*/api/auth/me', () => HttpResponse.error()));
    const { url, user } = renderApp('/app/cases', { sessionKnown: false });

    expect(await screen.findByText("Couldn't reach LexFlow")).toBeInTheDocument();
    expect(url()).toBe('/app/cases');
    server.resetHandlers();
    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByRole('heading', { name: 'Cases' })).toBeInTheDocument();
  });
});
