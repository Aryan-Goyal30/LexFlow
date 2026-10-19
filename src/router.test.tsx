import { screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from './test/renderApp';

describe('route guard and sign-in (mock auth)', () => {
  it('sends a signed-out visitor to sign-in, then to the case list', async () => {
    const { url, user } = renderApp('/app/cases', { signedIn: false });

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
    expect(url()).toBe('/');

    await user.click(screen.getByRole('button', { name: 'Sign in' }));

    await waitFor(() => expect(url()).toBe('/app/cases'));
    expect(await screen.findByRole('heading', { name: 'Cases' })).toBeInTheDocument();
  });

  it('returns to the originally requested page after sign-in', async () => {
    const { url, user } = renderApp('/app/cases/case-1005?tab=research', { signedIn: false });

    await user.click(await screen.findByRole('button', { name: 'Sign in' }));

    await waitFor(() => expect(url()).toBe('/app/cases/case-1005?tab=research'));
    // The workspace loads the case from the API before its tabs appear.
    expect(await screen.findByRole('tab', { name: /Research/ })).toHaveAttribute(
      'aria-selected',
      'true',
    );
  });

  it('requires an email and password before signing in', async () => {
    const { url, user } = renderApp('/', { signedIn: false });

    await user.clear(await screen.findByLabelText('Password'));
    await user.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(screen.getByRole('alert')).toHaveTextContent('Enter your email and password');
    expect(url()).toBe('/');
  });

  it('says plainly that sign-in is simulated', async () => {
    renderApp('/', { signedIn: false });
    expect(await screen.findByText(/only simulates sign-in/)).toBeInTheDocument();
    expect(screen.queryByText(/role-based access/i)).not.toBeInTheDocument();
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
