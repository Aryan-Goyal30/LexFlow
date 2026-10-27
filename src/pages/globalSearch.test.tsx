import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../test/renderApp';
import { ARYAN_EMAIL, problem, server } from '../test/mockApi';

// The top bar's search against the fake API, which applies the server's
// visibility rules and limits (server/tests/test_global_search.py checks the
// server itself).

const searchBox = () =>
  screen.findByRole('combobox', { name: 'Search cases, clients and documents' });

describe('Global search', () => {
  it('finds cases, clients and documents as you type and opens a case', async () => {
    const { user, url } = renderApp('/app/cases');
    await user.type(await searchBox(), 'Aarav');
    const results = await screen.findByRole('listbox', { name: 'Search results' });
    const option = await within(results).findByRole('option', {
      name: /LF-2026-0142 · Aarav Textiles/,
    });
    expect(within(results).getByText('Cases')).toBeVisible();
    await user.click(option);
    await waitFor(() => expect(url()).toMatch(/^\/app\/cases\/[^/?]+$/));
    expect(await searchBox()).toHaveValue('');
  });

  it('opens a document in its case with the keyboard', async () => {
    const { user, url } = renderApp('/app/cases');
    await user.type(await searchBox(), 'Statement of Claim');
    await screen.findByRole('option', { name: /Statement of Claim\.pdf/ });
    await user.keyboard('{ArrowDown}{ArrowUp}{Enter}');
    await waitFor(() => expect(url()).toMatch(/^\/app\/cases\/[^/?]+\?tab=documents$/));
  });

  it('shows only what you may see, says when nothing matches, and asks for two letters', async () => {
    const { user } = renderApp('/app/cases', { as: ARYAN_EMAIL });
    const box = await searchBox();
    await user.type(box, 'A');
    expect(await screen.findByText(/Type at least 2 characters/)).toBeVisible();
    await user.type(box, 'arav');
    expect(await screen.findByText(/No cases, clients or documents match “Aarav”/)).toBeVisible();
    await user.clear(box);
    await user.type(box, 'LF-20');
    const options = await screen.findAllByRole('option');
    expect(options.map((o) => o.textContent)).toEqual([
      expect.stringMatching(/^LF-2026-0361 · Sattvik Foods/),
    ]);
  });

  it('reports a failed search and can retry it', async () => {
    let failures = 1;
    server.use(
      http.get('*/api/search', () => {
        if (failures-- > 0) return problem(500, 'internal-error', 'The server had a problem.');
        return HttpResponse.json({ cases: [], clients: [], documents: [] });
      }),
    );
    const { user } = renderApp('/app/cases');
    await user.type(await searchBox(), 'Aarav');
    expect(await screen.findByRole('alert')).toHaveTextContent(/The search failed/);
    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText(/No cases, clients or documents match/)).toBeVisible();
  });

  it('offers no notifications in the top bar or the navigation', async () => {
    renderApp('/app/cases');
    await searchBox();
    expect(screen.queryByRole('button', { name: 'Notifications' })).toBeNull();
    expect(screen.queryByText('Notifications')).toBeNull();
    expect(screen.queryByText('Soon')).toBeNull();
  });
});
