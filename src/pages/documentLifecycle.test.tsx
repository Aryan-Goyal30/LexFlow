import { screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { renderApp } from '../test/renderApp';
import {
  ARYAN_EMAIL,
  MOCK_PARALEGAL_EMAIL,
  mockAddMember,
  mockApiState,
  server,
} from '../test/mockApi';

// Deleting documents is soft; the Administrator and the lead advocate can
// restore them. The server enforces it (server/tests/test_document_lifecycle.py).

const SATTVIK = 'case-1005';
const NOTICE = 'Cease and Desist Notice.pdf';

const pdf = (name = 'Rejoinder.pdf', text = '%PDF-1.4\n%%EOF\n') =>
  new File([text], name, { type: 'application/pdf' });

const liveList = () => screen.getByRole('list', { name: 'Case documents' });

afterEach(() => server.events.removeAllListeners());

describe('deleted documents', () => {
  it('lets the lead restore a removed document', async () => {
    const { user } = renderApp(`/app/cases/${SATTVIK}?tab=documents`, { as: ARYAN_EMAIL });
    await user.click(await screen.findByRole('button', { name: `Remove ${NOTICE}` }));
    await waitFor(() => expect(within(liveList()).queryByText(NOTICE)).toBeNull());

    const deleted = await screen.findByRole('list', { name: 'Deleted documents' });
    expect(within(deleted).getByText(/^Deleted .* by Aryan Goyal$/)).toBeVisible();
    await user.click(within(deleted).getByRole('button', { name: `Restore ${NOTICE}` }));

    expect(await screen.findByText(`Restored ${NOTICE}.`)).toBeVisible();
    await waitFor(() => expect(within(liveList()).getByText(NOTICE)).toBeVisible());
    expect(await screen.findByText('No deleted documents.')).toBeVisible();
  });

  it('explains why a document cannot be restored while its name is taken', async () => {
    const { user } = renderApp(`/app/cases/${SATTVIK}?tab=documents`);
    const picker = await screen.findByLabelText('Choose files to attach');
    await user.upload(picker, pdf());
    await user.click(await screen.findByRole('button', { name: 'Remove Rejoinder.pdf' }));
    await screen.findByRole('list', { name: 'Deleted documents' });
    await user.upload(picker, pdf('Rejoinder.pdf', '%PDF-1.4\n% second\n%%EOF\n'));
    await waitFor(() => expect(within(liveList()).getByText('Rejoinder.pdf')).toBeVisible());

    const deleted = screen.getByRole('list', { name: 'Deleted documents' });
    await user.click(within(deleted).getByRole('button', { name: 'Restore Rejoinder.pdf' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Rejoinder.pdf was not restored. Another document named Rejoinder.pdf is on this case.',
    );
    expect(within(deleted).getByText('Rejoinder.pdf')).toBeVisible();
  });

  it('shows who added each uploaded document', async () => {
    const { user } = renderApp(`/app/cases/${SATTVIK}?tab=documents`);
    await user.upload(await screen.findByLabelText('Choose files to attach'), pdf());
    const row = (await within(liveList()).findByText('Rejoinder.pdf')).closest('li');
    expect(row).toHaveTextContent('added by Test Administrator');
  });

  it('is not shown to a paralegal, who cannot restore', async () => {
    mockAddMember(SATTVIK, MOCK_PARALEGAL_EMAIL, 'paralegal');
    const requested: string[] = [];
    server.events.on('request:start', ({ request }) => {
      requested.push(new URL(request.url).pathname);
    });
    renderApp(`/app/cases/${SATTVIK}?tab=documents`, { as: MOCK_PARALEGAL_EMAIL });

    await screen.findByText(NOTICE);
    expect(screen.queryByRole('heading', { name: /Deleted Documents/ })).toBeNull();
    expect(requested.some((path) => path.endsWith('/documents/deleted'))).toBe(false);
    expect(mockApiState().cases.find((c) => c.id === SATTVIK)?.deletedDocuments).toEqual([]);
  });
});
