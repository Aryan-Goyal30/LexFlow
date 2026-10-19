import { act, screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../test/renderApp';
import { problem, server } from '../test/mockApi';
import { mockCases } from '../data/mockData';

describe('Case list', () => {
  it('shows a loading state, then the cases from the API', async () => {
    renderApp('/app/cases');

    expect(screen.getByRole('status')).toHaveTextContent('Loading cases');
    const rows = await screen.findAllByRole('row');
    expect(rows).toHaveLength(mockCases.length + 1);
    expect(
      screen.getByText(`${mockCases.length} matters on file.`, { exact: false }),
    ).toBeVisible();
  });

  it('labels fictional sample cases', async () => {
    renderApp('/app/cases');

    const rows = await screen.findAllByRole('row');
    for (const row of rows.slice(1)) {
      expect(within(row).getByText('Sample')).toBeInTheDocument();
    }
    expect(screen.getByText(/marked Sample are fictional/)).toBeInTheDocument();
  });

  it('shows an error with a working retry', async () => {
    server.use(
      http.get('*/api/cases', () =>
        problem(500, 'internal-error', 'Something broke on the server.'),
      ),
    );
    const { user } = renderApp('/app/cases');

    expect(await screen.findByText("Couldn't load the cases")).toBeInTheDocument();
    expect(screen.getByText('Something broke on the server.')).toBeInTheDocument();

    server.resetHandlers();
    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findAllByRole('row')).toHaveLength(mockCases.length + 1);
  });

  it('explains when the server cannot be reached', async () => {
    server.use(http.get('*/api/cases', () => HttpResponse.error()));
    renderApp('/app/cases');

    expect(await screen.findByText(/Can't reach the LexFlow server/)).toBeInTheDocument();
  });

  it('explains when the dev proxy answers for an API that is not running', async () => {
    // What Vite's proxy sends when nothing listens behind it: 500, empty body.
    server.use(
      http.get(
        '*/api/cases',
        () => new HttpResponse(null, { status: 500, headers: { 'Content-Type': 'text/plain' } }),
      ),
    );
    renderApp('/app/cases');

    expect(await screen.findByText(/Can't reach the LexFlow server/)).toBeInTheDocument();
  });

  it('keeps the list on screen when a later refresh fails', async () => {
    const { queryClient } = renderApp('/app/cases');
    expect(await screen.findAllByRole('row')).toHaveLength(mockCases.length + 1);
    server.use(http.get('*/api/cases', () => problem(500, 'internal-error', 'Refresh failed.')));

    await act(() => queryClient.invalidateQueries());

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /Couldn't refresh.*Refresh failed\./,
    );
    expect(screen.getAllByRole('row')).toHaveLength(mockCases.length + 1);
  });

  it('distinguishes an empty database from a search with no matches', async () => {
    server.use(http.get('*/api/cases', () => HttpResponse.json([])));
    renderApp('/app/cases');

    expect(await screen.findByText('No cases yet')).toBeInTheDocument();
    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument();
    expect(screen.queryByText('No matching cases')).not.toBeInTheDocument();
  });

  it('searches and filters the loaded cases', async () => {
    const { user } = renderApp('/app/cases');
    await screen.findAllByRole('row');

    await user.type(screen.getByRole('searchbox', { name: 'Search cases' }), 'sattvik');
    expect(screen.getAllByRole('row')).toHaveLength(2);

    await user.clear(screen.getByRole('searchbox', { name: 'Search cases' }));
    await user.click(screen.getByRole('button', { name: 'Closed' }));
    expect(screen.getAllByRole('row')).toHaveLength(2);
    expect(screen.getByRole('button', { name: 'Closed' })).toHaveAttribute('aria-pressed', 'true');

    await user.type(screen.getByRole('searchbox', { name: 'Search cases' }), 'no such matter');
    expect(screen.getByText('No matching cases')).toBeInTheDocument();
    expect(screen.queryByText('No cases yet')).not.toBeInTheDocument();
  });

  it('shows next hearing and document count from the API', async () => {
    renderApp('/app/cases');

    const link = await screen.findByRole('link', { name: /Sattvik Foods Pvt\. Ltd\. v\./ });
    const row = link.closest('tr') as HTMLElement;
    expect(within(row).getByText('Sep 30, 2026')).toBeInTheDocument();
    expect(within(row).getByText('4')).toBeInTheDocument();
  });
});

describe('Practice Overview', () => {
  it('shows loading states, then empty states for an empty database', async () => {
    server.use(
      http.get('*/api/cases', () => HttpResponse.json([])),
      http.get('*/api/hearings/upcoming', () => HttpResponse.json([])),
    );
    renderApp('/app/dashboard');

    const loading = screen.getAllByRole('status').map((s) => s.textContent);
    expect(loading).toEqual(['Loading case counts…', 'Loading hearings…']);
    expect(await screen.findByText('No cases yet.')).toBeInTheDocument();
    expect(await screen.findByText(/^No upcoming hearings\./)).toBeInTheDocument();
    expect(screen.getByText('Total Cases').parentElement).toHaveTextContent('0');
  });
  it('loads counts and hearings independently', async () => {
    server.use(
      http.get('*/api/hearings/upcoming', () => problem(500, 'internal-error', 'Hearings down.')),
    );
    renderApp('/app/dashboard');

    // Counts still load although the hearings panel failed.
    expect(await screen.findByText('Total Cases')).toBeInTheDocument();
    expect(screen.getByText("Couldn't load hearings")).toBeInTheDocument();
    expect(screen.getByText('Hearings down.')).toBeInTheDocument();
    expect(screen.getByText(String(mockCases.length))).toBeInTheDocument();
  });

  it('shows the case-count error without hiding the hearings panel', async () => {
    server.use(http.get('*/api/cases', () => problem(500, 'internal-error', 'Cases down.')));
    renderApp('/app/dashboard');

    expect(await screen.findByText("Couldn't load the cases")).toBeInTheDocument();
    expect(screen.getByText('Upcoming Hearings')).toBeInTheDocument();
  });

  it('lists upcoming hearings from the API', async () => {
    server.use(
      http.get('*/api/hearings/upcoming', () =>
        HttpResponse.json([
          {
            id: 'h-x',
            date: '2099-01-15',
            time: null,
            court: 'To be notified',
            purpose: 'First listing',
            isSample: false,
            caseId: 'case-1005',
            caseTitle: 'Test listing',
            caseNumber: 'LF-2099-0001',
          },
        ]),
      ),
    );
    renderApp('/app/dashboard');

    expect(await screen.findByText('First listing')).toBeInTheDocument();
    expect(screen.getByText(/Jan 15, 2099 · time to be confirmed · To be notified/)).toBeVisible();
  });
});
