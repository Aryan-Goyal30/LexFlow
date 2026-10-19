import { screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { renderApp } from '../test/renderApp';
import { ARYAN_EMAIL, mockAddMember, mockAddUser } from '../test/mockApi';

// What each role sees. The server enforces all of it (server/tests/test_case_access.py);
// these tests check that the screens offer only what the server allows.

const PARALEGAL = 'para@lexflow.test';
const OUTSIDER = 'rajat.deshpande@lexflow.test'; // leads a different sample case

describe('a Paralegal on the Sattvik case team', () => {
  beforeEach(() => {
    mockAddUser({ email: PARALEGAL, role: 'Paralegal', name: 'Priya Paralegal' });
    mockAddMember('case-1005', PARALEGAL, 'paralegal');
  });

  it('sees only that case, and no way to open new ones', async () => {
    renderApp('/app/cases', { as: PARALEGAL });

    const rows = await screen.findAllByRole('row');
    expect(rows).toHaveLength(2); // header + the one case
    expect(
      within(rows[1]).getByRole('link', { name: /Sattvik Foods Pvt\. Ltd\. v\./ }),
    ).toBeVisible();
    expect(screen.queryByRole('link', { name: /New Case/ })).toBeNull();
  });

  it('is told that opening a case is for advocates', async () => {
    renderApp('/app/cases/new', { as: PARALEGAL });
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Opening a case is for administrators and advocates',
    );
    expect(screen.queryByRole('form')).toBeNull();
  });

  it('can add documents but not remove them', async () => {
    renderApp('/app/cases/case-1005?tab=documents', { as: PARALEGAL });

    expect(await screen.findByText('Your access: Paralegal on the case team')).toBeVisible();
    expect(screen.getByLabelText('Choose files to attach')).toBeInTheDocument();
    expect(screen.getByText('Cease and Desist Notice.pdf')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Remove / })).toBeNull();
  });
});

describe('an Advocate', () => {
  it('sees the cases they lead and opens new ones only as lead', async () => {
    const { user } = renderApp('/app/cases', { as: ARYAN_EMAIL });
    const rows = await screen.findAllByRole('row');
    expect(rows).toHaveLength(2); // Aryan Goyal leads one sample case

    await user.click(screen.getByRole('link', { name: /New Case/ }));
    const lead = await screen.findByLabelText('Lead Advocate');
    expect(lead).toHaveDisplayValue('Aryan Goyal');
    expect(lead).toBeDisabled();
    expect(screen.getByText('You lead the cases you open.')).toBeInTheDocument();
  });

  it('gets "Case not found" for a case of someone else', async () => {
    mockAddUser({ email: OUTSIDER, role: 'Advocate', name: 'Rajat Deshpande' });
    renderApp('/app/cases/case-1005', { as: OUTSIDER });
    expect(await screen.findByRole('heading', { name: 'Case not found' })).toBeInTheDocument();
  });
});

describe('an Administrator', () => {
  it('sees every case, removes documents and picks any lead', async () => {
    const { user } = renderApp('/app/cases/case-1005?tab=documents');

    expect(await screen.findByText('Your access: Administrator: full access')).toBeVisible();
    expect(
      screen.getByRole('button', { name: 'Remove Cease and Desist Notice.pdf' }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole('link', { name: /All Cases/ }));
    await user.click(await screen.findByRole('link', { name: /New Case/ }));
    await waitFor(() => expect(screen.getByLabelText('Lead Advocate')).toBeEnabled());
  });
});
