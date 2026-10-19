import { screen, waitFor, within } from '@testing-library/react';
import { delay, http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../test/renderApp';
import { mockApiState, problem, server } from '../test/mockApi';
import { mockCases, mockClients } from '../data/mockData';
import { todayIsoDate } from '../lib/format';

const futureDate = todayIsoDate(new Date(Date.now() + 30 * 24 * 60 * 60 * 1000));

async function fillValidForm(user: ReturnType<typeof renderApp>['user']) {
  await user.type(await screen.findByLabelText(/Case Title/), 'Test Matter v. Other Party');
  await user.selectOptions(screen.getByLabelText(/Client/), mockClients[2].id);
  await user.type(screen.getByLabelText(/Summary/), 'A summary long enough to pass.');
  await user.type(screen.getByLabelText('Next Hearing Date'), futureDate);
}

describe('New case form', () => {
  it('loads clients and advocates from the API', async () => {
    renderApp('/app/cases/new');

    expect(screen.getByRole('status')).toHaveTextContent('Loading clients and advocates');
    const client = await screen.findByLabelText(/Client/);
    expect(within(client).getAllByRole('option')).toHaveLength(mockClients.length + 1);
    // Sample records are labelled as such.
    expect(
      within(client).getByRole('option', { name: /Aarav Textiles.*\(sample\)/ }),
    ).toBeVisible();
    // Defaults to the signed-in (demo) advocate.
    expect(screen.getByLabelText('Lead Advocate')).toHaveDisplayValue('Aryan Goyal');
  });

  it('shows an error with a retry when the form data cannot load', async () => {
    server.use(http.get('*/api/clients', () => problem(503, 'internal-error', 'Database down.')));
    const { user } = renderApp('/app/cases/new');

    expect(await screen.findByText("Couldn't load the form")).toBeInTheDocument();
    expect(screen.getByText('Database down.')).toBeInTheDocument();

    server.resetHandlers();
    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByLabelText(/Case Title/)).toBeInTheDocument();
  });

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
    expect(mockApiState().cases).toHaveLength(mockCases.length); // nothing was sent
  });

  it('rejects a next hearing date in the past', async () => {
    const { url, user } = renderApp('/app/cases/new');

    await fillValidForm(user);
    await user.clear(screen.getByLabelText('Next Hearing Date'));
    await user.type(screen.getByLabelText('Next Hearing Date'), '2000-01-01');
    await user.click(screen.getByRole('button', { name: 'Create Case' }));

    expect(screen.getByLabelText('Next Hearing Date')).toHaveAccessibleDescription(
      /cannot be in the past/,
    );
    expect(url()).toBe('/app/cases/new');
  });

  it('creates the case on the server, opens its Documents tab, and lists it first', async () => {
    const { url, user } = renderApp('/app/cases/new');

    await fillValidForm(user);
    await user.click(screen.getByRole('button', { name: 'Create Case' }));

    await waitFor(() => expect(url()).toMatch(/^\/app\/cases\/case-new-\d+\?tab=documents$/));
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Test Matter v. Other Party' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Documents/ })).toHaveAttribute('aria-selected', 'true');
    // Saved on the server, with the advocate's id rather than a name.
    const saved = mockApiState().cases.at(-1);
    expect(saved?.title).toBe('Test Matter v. Other Party');
    expect(saved?.leadAttorney).toBe('Aryan Goyal');

    await user.click(screen.getByRole('link', { name: /All Cases/ }));
    const rows = await screen.findAllByRole('row');
    // Header row, then the new case first, then the sample cases.
    expect(rows).toHaveLength(mockCases.length + 2);
    expect(within(rows[1]).getByText('Test Matter v. Other Party')).toBeInTheDocument();
    expect(within(rows[1]).getByText(mockClients[2].name)).toBeInTheDocument();
  });

  it('shows the submitting state and ignores repeat clicks', async () => {
    let requests = 0;
    server.use(
      http.post('*/api/cases', async () => {
        requests += 1;
        await delay(200);
        return HttpResponse.json(mockApiState().cases[0], { status: 201 });
      }),
    );
    const { user } = renderApp('/app/cases/new');
    await fillValidForm(user);

    await user.click(screen.getByRole('button', { name: 'Create Case' }));
    const saving = screen.getByRole('button', { name: /Creating case/ });
    expect(saving).toBeDisabled();
    await user.click(saving);

    await waitFor(() => expect(screen.queryByRole('button', { name: /Creating case/ })).toBeNull());
    expect(requests).toBe(1);
  });

  it('puts server validation errors beside their fields and keeps the input', async () => {
    server.use(
      http.post('*/api/cases', () =>
        problem(422, 'validation-error', 'Correct the highlighted fields and try again.', [
          { field: 'title', message: 'A case with this title is not allowed.' },
          { field: 'nextHearing', message: 'The next hearing date cannot be in the past.' },
        ]),
      ),
    );
    const { url, user } = renderApp('/app/cases/new');
    await fillValidForm(user);

    await user.click(screen.getByRole('button', { name: 'Create Case' }));

    const title = await screen.findByLabelText(/Case Title/);
    await waitFor(() =>
      expect(title).toHaveAccessibleDescription('A case with this title is not allowed.'),
    );
    expect(screen.getByLabelText('Next Hearing Date')).toHaveAccessibleDescription(
      /cannot be in the past/,
    );
    expect(title).toHaveFocus();
    expect(title).toHaveValue('Test Matter v. Other Party'); // nothing typed is lost
    expect(screen.getByLabelText(/Summary/)).toHaveValue('A summary long enough to pass.');
    expect(url()).toBe('/app/cases/new');
  });

  it('keeps the form and explains when the server cannot be reached', async () => {
    server.use(http.post('*/api/cases', () => HttpResponse.error()));
    const { url, user } = renderApp('/app/cases/new');
    await fillValidForm(user);

    await user.click(screen.getByRole('button', { name: 'Create Case' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /The case was not created\. Can't reach the LexFlow server/,
    );
    expect(screen.getByLabelText(/Case Title/)).toHaveValue('Test Matter v. Other Party');
    expect(url()).toBe('/app/cases/new');
  });
});
